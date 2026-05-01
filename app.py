from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import os
import uuid
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from docx import Document
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
CHROMA_DIR = "chroma_db"

# Your Groq API key
import os
LLM_API_KEY = os.getenv("GROQ_API_KEY")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

# Groq client
client = OpenAI(
    api_key=LLM_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Free local embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# ChromaDB
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection("documents")


# ----------------------------------
# Extract text from uploaded files
# ----------------------------------
def extract_text(filepath):
    text = ""

    if filepath.endswith(".pdf"):
        reader = PdfReader(filepath)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    elif filepath.endswith(".docx"):
        doc = Document(filepath)
        for para in doc.paragraphs:
            text += para.text + "\n"

    elif filepath.endswith(".txt"):
        with open(filepath, "r", encoding="utf-8") as file:
            text = file.read()

    return text.strip()


# ----------------------------------
# Split text into chunks
# ----------------------------------
def create_chunks(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    return splitter.split_text(text)


# ----------------------------------
# Create local embeddings
# ----------------------------------
def get_embedding(text):
    return embedding_model.encode(text).tolist()


# ----------------------------------
# Home page
# ----------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ----------------------------------
# Upload route
# ----------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    try:
        file = request.files["file"]

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        text = extract_text(filepath)

        if not text:
            return jsonify({"message": "No text found in file."})

        chunks = create_chunks(text)

        print("Uploaded:", file.filename)
        print("Chunks created:", len(chunks))

        for chunk in chunks:
            embedding = get_embedding(chunk)

            collection.add(
                ids=[str(uuid.uuid4())],
                documents=[chunk],
                embeddings=[embedding],
                metadatas=[{"source": file.filename}]
            )

        return jsonify({"message": "File uploaded successfully"})

    except Exception as e:
        print("UPLOAD ERROR:", e)
        return jsonify({"message": f"Upload failed: {str(e)}"})


# ----------------------------------
# Chat route
# ----------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_question = request.json["message"]

        question_embedding = get_embedding(user_question)

        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=5
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        if docs and len(docs) > 0:
            context = "\n\n".join(docs)
            source = metas[0]["source"]

            prompt = f"""
You are a document assistant.

Answer ONLY using the document content below.

DOCUMENT:
{context}

QUESTION:
{user_question}

Rules:
- Give a clear answer
- If user asks for summary, summarize the document
- If user asks for a topic number, find that topic
- If answer not found, reply:
I could not find this information in the uploaded files.
"""

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            answer = response.choices[0].message.content
            answer += f"\n\n(Source: {source})"

        else:
            answer = "I could not find this information in the uploaded files."

        return jsonify({"reply": answer})

    except Exception as e:
        print("CHAT ERROR:", e)
        return jsonify({"reply": f"Error: {str(e)}"})


# ----------------------------------
# Run app
# ----------------------------------
if __name__ == "__main__":
    app.run(debug=True)