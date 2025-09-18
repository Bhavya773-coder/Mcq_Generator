import streamlit as st
from pptx import Presentation
import torch
from transformers import AutoTokenizer, AutoModel
import io
import json
import ollama
import pandas as pd
import re

# -------------------------
# Device Setup (CPU only)
# -------------------------
device = torch.device("cpu")

# -------------------------
# Embedding Model Setup
# -------------------------
def load_model():
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2").to(device)
    return tokenizer, model

def get_embeddings(texts, tokenizer, model):
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt").to(device)
    with torch.no_grad():
        embeddings = model(**inputs).last_hidden_state.mean(dim=1)
    return embeddings  # stays on CPU

# -------------------------
# Extract text from PPTX
# -------------------------
def extract_text_from_pptx(file):
    prs = Presentation(file)
    all_text = []
    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                slide_text.append(shape.text.strip())
        if slide_text:
            all_text.append(f"--- Slide {slide_num} ---\n" + "\n".join(slide_text))
    return "\n\n".join(all_text)

# -------------------------
# Generate MCQs in Batches (Optimized)
# -------------------------
def generate_mcqs_in_batches(text, total_questions=50, batch_size=10, seed=None):
    all_mcqs = []
    num_batches = (total_questions + batch_size - 1) // batch_size  # ceiling division

    # Split text into chunks for variety across batches
    text_chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    if not text_chunks:
        text_chunks = [text]

    for i in range(num_batches):
        questions_to_generate = min(batch_size, total_questions - len(all_mcqs))
        st.info(f"🔄 Generating batch {i+1}/{num_batches} ({questions_to_generate} MCQs)...")

        # Rotate text chunks for variety
        content = text_chunks[i % len(text_chunks)]

        prompt = f"""
        Based on the following content, generate {questions_to_generate} exam-quality multiple-choice questions (MCQs).
        Each MCQ must include:
        - A clear question
        - Four options (A, B, C, D)
        - The correct answer (just the letter)
        - Number the MCQs as Q1, Q2, etc.

        Return ONLY a JSON array like this:
        [
          {{
            "question": "Q1. Question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": "A"
          }}
        ]

        Content:
        {content}
        """

        try:
            response = ollama.chat(
                model="llama3.1",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.4, "seed": seed} if seed else {"temperature": 0.4}
            )
            output = response['message']['content']
            json_match = re.search(r'\[.*\]', output, re.DOTALL)
            if json_match:
                mcqs = json.loads(json_match.group(0))
                all_mcqs.extend(mcqs)
            else:
                st.warning(f"⚠️ Batch {i+1} did not return valid JSON.")
        except Exception as e:
            st.error(f"❌ Error in batch {i+1}: {e}")

    # -------------------------
    # Ensure exact required number
    # -------------------------
    if len(all_mcqs) > total_questions:
        all_mcqs = all_mcqs[:total_questions]
    elif len(all_mcqs) < total_questions:
        # If fewer generated, duplicate some with new numbering
        needed = total_questions - len(all_mcqs)
        filler = all_mcqs[:needed] if all_mcqs else []
        all_mcqs.extend(filler)

    # Re-number to maintain consistency
    for i, mcq in enumerate(all_mcqs, start=1):
        qtext = mcq.get("question", "")
        # Ensure prefix like Q1., Q2., etc.
        if not qtext.strip().lower().startswith("q"):
            mcq["question"] = f"Q{i}. {qtext}"
        else:
            mcq["question"] = f"Q{i}. {qtext.split('.', 1)[-1].strip()}"

    return all_mcqs

# -------------------------
# Convert MCQs to Excel
# -------------------------
def mcqs_to_excel(mcqs):
    data = []
    for i, mcq in enumerate(mcqs, start=1):
        question = mcq.get("question", "")
        options = mcq.get("options", [])
        answer = mcq.get("answer", "")

        while len(options) < 4:
            options.append("")
        options = options[:4]

        data.append([
            i, question, options[0], options[1], options[2], options[3], answer
        ])

    df = pd.DataFrame(data, columns=["Q.No", "Question", "Option A", "Option B", "Option C", "Option D", "Answer"])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="MCQs")
    output.seek(0)
    return output

# -------------------------
# Convert MCQs to JSON
# -------------------------
def mcqs_to_json(mcqs):
    return io.BytesIO(json.dumps(mcqs, indent=2).encode("utf-8"))

# -------------------------
# Streamlit UI
# -------------------------
st.title("📊 PPTX to MCQ Generator")

uploaded_file = st.file_uploader("Upload a PowerPoint (.pptx) file", type=["pptx"])

if uploaded_file is not None:
    with st.spinner("Extracting text..."):
        ppt_text = extract_text_from_pptx(uploaded_file)
        st.subheader("📄 Extracted Text:")
        st.text_area("Text Output", ppt_text, height=300)

        # Save text as .txt
        text_file = io.BytesIO(ppt_text.encode("utf-8"))
        st.download_button(
            label="⬇ Download Extracted Text",
            data=text_file,
            file_name="extracted_ppt_text.txt",
            mime="text/plain"
        )

        # MCQ Generation options
        st.subheader("MCQ Generation Options")
        num_mcqs = st.slider("Select number of MCQs to generate", min_value=10, max_value=100, step=10, value=20)
        seed_value = st.number_input("Seed value (optional)", min_value=0, step=1, value=0)

        if st.button("Generate MCQs"):
            with st.spinner(f"Generating {num_mcqs} MCQs in batches..."):
                mcqs = generate_mcqs_in_batches(
                    ppt_text,
                    total_questions=num_mcqs,
                    batch_size=10,
                    seed=seed_value if seed_value > 0 else None
                )

            if not mcqs:
                st.error("⚠️ MCQ generation failed.")
            else:
                st.success(f"✅ Successfully generated {len(mcqs)} MCQs!")
                st.subheader("📝 Generated MCQs Preview:")
                st.json(mcqs[:5])  # Preview first 5

                excel_file = mcqs_to_excel(mcqs)
                json_file = mcqs_to_json(mcqs)

                if excel_file:
                    st.download_button(
                        label=f"⬇ Download {len(mcqs)} MCQs (Excel)",
                        data=excel_file,
                        file_name=f"generated_{len(mcqs)}_mcqs.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                if json_file:
                    st.download_button(
                        label=f"⬇ Download {len(mcqs)} MCQs (JSON)",
                        data=json_file,
                        file_name=f"generated_{len(mcqs)}_mcqs.json",
                        mime="application/json"
                    )

# Sidebar
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    1. Upload a PowerPoint (.pptx) file  
    2. Text will be extracted automatically  
    3. Choose how many MCQs to generate (10–100)  
    4. Optionally set a **seed value** for reproducibility  
    5. MCQs will be generated in **batches of 10**  
    6. Download the MCQs as **Excel or JSON**  

    **Note:** Requires Ollama with llama3.1 model installed locally.
    """)
    if st.button("Check Ollama Status"):
        try:
            models = ollama.list()
            st.success("✅ Ollama is running!")
            st.write("Available models:", [model['name'] for model in models['models']])
        except:
            st.error("❌ Ollama is not available. Please install and start Ollama.")