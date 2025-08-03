import pandas as pd
import psycopg2
from time import time
import os
from dotenv import load_dotenv, find_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from rag_utils import *

import warnings
warnings.filterwarnings("ignore", message="No sentence-transformers model found*")
import logging
logging.getLogger("sentence_transformers.SentenceTransformer").setLevel(logging.ERROR)

load_dotenv(find_dotenv())
pg_user = os.getenv("PG_USER")
pg_password = os.getenv("PG_PASSWORD")

def ingest_data(df):
    conn = psycopg2.connect(
        dbname="vector_db",
        user=pg_user,
        password=pg_password,
        host="localhost",
        port=5432
    )
    cursor = conn.cursor()

    start_time = time()
    data_ingested = 0

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    for _, row in df.iterrows():
        full_text = row['detail_content']
        
        # Split long articles
        chunks = text_splitter.split_text(full_text)
        
        # Add chunks as Documents
        for i, chunk in enumerate(chunks):
            page_content=f"\nTanggal terbit : {row['date_publish']}\nJudul : {row['title']}\n\n{chunk}"
            title = row['title']
            date_publish = row['date_publish']
            publiser = row['publiser']
            author = row['author']
            doc_id = _
            chunk_id = i
            vector = embed_text(page_content)

            cursor.execute(
                "INSERT INTO documents (doc_id, chunk_id, title, publisher, publish_date, author, content, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (doc_id, chunk_id, title, publiser, date_publish, author, page_content, vector)
            )
            conn.commit()
            data_ingested += 1
    conn.close()
    end_time = time()
    print(f'TOTAL DATA INTSERT : {data_ingested}')
    print('Inserted data to database, took %.3f second' % (end_time - start_time))

def pg_vector_ingest(df):
    start_time = time()

    # Format data into Document Langchain
    docs = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    for _, row in df.iterrows():
        full_text = row['detail_content']
        
        # Split long articles
        chunks = text_splitter.split_text(full_text)

        # Add chunks as Documents
        for i, chunk in enumerate(chunks):
            doc = Document(
                    page_content=f"\nTanggal terbit : {str(row['date_publish'])}\nPenulis : {row['author']}\nJudul : {row['title']}\n\n{chunk}",
                    metadata={
                        "title": row['title'],
                        "date_published": str(row['date_publish']),
                        "publiser" : row['publiser'],
                        "author" : row['author']
                        }
                    )
            docs.append(doc)
    
    # Create and store the vectorstore
    connection_string = f"postgresql+psycopg2://{pg_user}:{pg_password}@localhost:5432/vector_db"
    collection_name = "pg_vectorstore"

    hf_embedding = HuggingFaceEmbeddings(
        model_name="indobenchmark/indobert-base-p1"
    )

    vectorstore = PGVector.from_documents(
        documents=docs,
        embedding=hf_embedding,
        collection_name=collection_name,
        connection_string=connection_string
    )

    end_time = time()
    print('Data Successfully store!')
    print('Inserted data to database, took %.3f second' % (end_time - start_time))


# Declare local path
df = df = pd.read_json('data.json')
df['date_publish'] = df['date_publish'].apply(lambda x : format_date(x))
df['detail_content'] = df['detail_content'].apply(lambda x : format_content(x) if len(x) != 0 else x)

print('-----------------Ingest data to postgres vector-db-------------------')
pg_vector_ingest(df)
