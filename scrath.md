1. create chat template
2. try to use chat history

docker exec -it vectordb psql -U admin -d vector_db

CREATE TABLE documents (
  doc_id TEXT,
  chunk_id TEXT,
  title TEXT,
  publisher TEXT,
  publish_date TIMESTAMP,
  author TEXT,
  content TEXT,
  embedding VECTOR(768)
);


loop chain
- cara agar konteks tidak digunakan jika perbincangan ringan
- rule kapan harus pakai relevan docs, kapan tidak

https://fastapi.tiangolo.com/tutorial/sql-databases/

uvicorn main:app --reload 
uvicorn module(py file):instance --reload(if you want to automate reload after module update)

path = need to write down in decorator
parameter = only need to write as function param

models is more like a table blueprint, use for interact with db. 
schema is a template for how the result should be showed or inputs. like for request or response

the key concept is ORM, object relational mapping. so each instance in script(database) is represent a table in a database

post = request
get = response
delete = delete
put = update

uvicorn blog.main:app --reload --host 127.0.0.1 --port 9000


NEXT IS STREAMLIT

uvicorn main:app --reload --host 127.0.0.1 --port 9000
