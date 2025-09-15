import os
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain.vectorstores import FAISS, Chroma
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

# === CONFIGURATION ===
DATA_DIR = "C:\Users\sanke\Desktop\Python\scraped_pages"  # Folder containing .md files
USE_FAISS = True             # Set False to use Chroma
USE_OPENAI = True            # Set False to use HuggingFace
CHROMA_DIR = "chroma_store"  # Persistent Chroma directory

# === STEP 1: Load Markdown Files ===
def load_markdown_files(folder_path):
    docs = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            loader = TextLoader(os.path.join(folder_path, filename), encoding="utf-8")
            docs.extend(loader.load_and_split())
    return docs

# === STEP 2: Split into Chunks ===
def chunk_documents(documents):
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_documents(documents)

# === STEP 3: Choose Embedding Model ===
def get_embedding_model():
    if USE_OPENAI:
        return OpenAIEmbeddings()
    else:
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# === STEP 4: Create Vector Store ===
def create_vector_store(chunks, embedding_model):
    if USE_FAISS:
        return FAISS.from_documents(chunks, embedding_model)
    else:
        return Chroma.from_documents(chunks, embedding_model, persist_directory=CHROMA_DIR)

# === STEP 5: Build QA Chain ===
def build_qa_chain(vector_store):
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})
    llm = OpenAI(temperature=0)
    return RetrievalQA.from_chain_type(llm=llm, retriever=retriever, return_source_documents=True)

# === MAIN EXECUTION ===
if __name__ == "__main__":
    print("🔍 Loading markdown files...")
    raw_docs = load_markdown_files(DATA_DIR)

    print("✂️ Splitting into chunks...")
    chunks = chunk_documents(raw_docs)

    print("🧠 Generating embeddings...")
    embedding_model = get_embedding_model()

    print(f"📦 Storing vectors in {'FAISS' if USE_FAISS else 'Chroma'}...")
    vector_store = create_vector_store(chunks, embedding_model)

    print("🤖 Building RetrievalQA pipeline...")
    qa_chain = build_qa_chain(vector_store)

    # === INTERACTIVE QUERY LOOP ===
    print("\n✅ Ready! Ask your questions below (type 'exit' to quit):")
    while True:
        query = input("\n🗣️ Your question: ")
        if query.lower() in ["exit", "quit"]:
            break
        result = qa_chain(query)
        print("\n📄 Answer:")
        print(result["result"])