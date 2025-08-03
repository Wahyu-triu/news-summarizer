import streamlit as st
import requests
import time

API_URL = "http://localhost:9000/post"

st.title('News Summarizer 📰')

st.divider()

chat_requests = {
    'question' : None
}

with st.form(key='prompt_from'):
    st.write('### Ask your question here:')
    chat_requests['question'] = st.text_input('Type your question here...')

    submit_button = st.form_submit_button(label='Submit Question')
    if submit_button:
        st.write('### AI Answer:')
        if not chat_requests['question']:
            st.warning('Please type your question')
        else:
            with st.spinner("Let the AI thinking first ..."):
                # Send POST request
                response = requests.post(API_URL, json=chat_requests)
                time.sleep(1.5)

                try:
                    # Show the response
                    if response.status_code == 200:
                        st.success("There it is!")
                        data = response.json()
                        st.text(data['answer'])

                except:
                    st.error(f"Request failed with status code {response.status_code}")
                    st.text(response.text)