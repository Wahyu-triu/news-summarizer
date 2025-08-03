from langchain_core.documents import Document
from datetime import datetime, date
from sentence_transformers import SentenceTransformer
import psycopg2
from docx import Document

import warnings
warnings.filterwarnings("ignore", message="No sentence-transformers model found*")
import logging
logging.getLogger("sentence_transformers.SentenceTransformer").setLevel(logging.ERROR)

def format_data(title, content, author, publisher, publish_date):
    # page_content=f"\nTanggal terbit : {str(publish_date)}\nPenulis : {author}\nJudul : {title}\n\n{content}",
    # metadata={
    #     "title": title,
    #     "date_published": str(publish_date),
    #     "publisher": publisher,
    #     "author" : author
    # }
    # doc = Document(page_content=page_content, metadata=metadata)
    doc = Document(
            page_content=f"\nTanggal terbit : {str(publish_date)}\nPenulis : {author}\nJudul : {title}\n\n{content}",
            metadata={
                "title": title,
                "date_published": str(publish_date),
                "publisher": publisher,
                "author" : author
            }
        )
    return doc

# Original string
def format_date(date_str):
    bulan_mapping = {
    'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr',
    'Mei': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Agu': 'Aug',
    'Sep': 'Sep', 'Okt': 'Oct', 'Nov': 'Nov', 'Des': 'Dec'
    }

    for indo, eng in bulan_mapping.items():
        if indo in date_str:
            date_str = date_str.replace(indo, eng)
            break
            
    # Remove the day name and timezone
    try:
        cleaned_str = date_str.split(', ')[1].replace(' WIB', '')
        dt = datetime.strptime(cleaned_str, "%d %b %Y %H:%M")
        formatted_date = dt.strftime("%Y-%m-%d")
    except:
        formatted_date = date.today().isoformat()
    return formatted_date

def format_content(content):
    splited_content = content.split('\n')

    clean_up_keyword = [
        'CONTINUE WITH CONTENT', 'ADVERTISEMENT', 'recommended by', 'di sini Selengkapnya', 'Simak juga Video'
    ]

    try:
        for s in splited_content:
            for c in clean_up_keyword:
                if c.lower() in s.lower():
                    splited_content = [x for x in splited_content if x != s]
    except:
        splited_content = splited_content

    final_string = '\n'.join(s.lower() for s in splited_content)

    splited_string = final_string.split('baca juga:')[:-1]
    clean_splited_string = []
    for i, s in enumerate(splited_string):
        if i != 0:
            s = s.split('\n')[2:]
            s = ' '.join(x for x in s)
        clean_splited_string.append(s)
    final_string = ' '.join(c for c in clean_splited_string)
    return final_string

def embed_text(text):
    model = SentenceTransformer("indobenchmark/indobert-base-p1")  # or any other embedding model
    embedding = model.encode(text).tolist()  # This gives a vector (NumPy array)
    return embedding

def get_vector_from_db(query):
    docs = []
    query_embedding = embed_text(query)

    conn = psycopg2.connect(
        dbname="vector_db",
        user="admin",
        password="admin",
        host="localhost",
        port=5432
    )
    cursor = conn.cursor()

    # Use cosine similarity to search in PostgreSQL using pgvector
    cursor.execute("""
        SELECT title, publisher, publish_date, author, content, embedding
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT 10;
    """, (query_embedding,))
    results = cursor.fetchall()
    for row in results:
        title, publisher, publish_date, author, content = row[0], row[1], row[2], row[3], row[4] 
        doc = format_data(title, content, author, publisher, publish_date)
        docs.append(doc)
    return docs

def extract_qa_pairs(file_path):
    doc = Document(file_path)
    qa_pairs = []

    for table in doc.tables:
        for row in table.rows:
            print(row.cells)
            if len(row.cells) >= 2:
                question = row.cells[0].text.strip()
                answer = row.cells[1].text.strip()
                if question and answer:
                    qa_pairs.append((question, answer))

    return qa_pairs

