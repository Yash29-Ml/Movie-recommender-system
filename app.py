import streamlit as st
import pickle
import pandas as pd
import requests
import time
import concurrent.futures


# Fetch movie details with retries and error handling
@st.cache_data(show_spinner=False)
def fetch_cached_movie_details(movie_id):
    return fetch_movie_details(movie_id)


def fetch_movie_details(movie_id, retries=3, delay=5):
    api_key = '8d45dcb1eefec0761446c65d574e58a6'  # Replace with your actual API key
    if not api_key:
        return {"error": "API key is missing."}

    movie_url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&language=en-US'
    credits_url = f'https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={api_key}&language=en-US'
    image_base_url = 'https://image.tmdb.org/t/p/w500'  # Medium size image

    for attempt in range(retries):
        try:
            movie_response = requests.get(movie_url, timeout=10)
            credits_response = requests.get(credits_url, timeout=10)

            # Check if the requests were successful
            if movie_response.status_code != 200 or credits_response.status_code != 200:
                return {"error": f"Error {movie_response.status_code} fetching movie details."}

            movie_data = movie_response.json()
            credits_data = credits_response.json()

            poster_path = movie_data.get('poster_path')
            poster_url = f'{image_base_url}/{poster_path}' if poster_path else "https://via.placeholder.com/500x750?text=Poster+Not+Found"
            title = movie_data.get('title', 'Unknown Title')
            rating = movie_data.get('vote_average', 'N/A')
            release_date = movie_data.get('release_date', 'Unknown')
            plot = movie_data.get('overview', 'Plot not available.')

            director_data = next((member for member in credits_data['crew'] if member['job'] == 'Director'), None)
            director_name = director_data['name'] if director_data else 'Unknown'
            director_image_path = director_data['profile_path'] if director_data and director_data.get(
                'profile_path') else None
            director_image_url = f'{image_base_url}/{director_image_path}' if director_image_path else "https://via.placeholder.com/500x500?text=No+Image"

            cast_members = []
            for cast_member in credits_data.get('cast', [])[:3]:
                cast_name = cast_member.get('name', 'Unknown')
                cast_image_path = cast_member.get('profile_path')
                cast_image_url = f'{image_base_url}/{cast_image_path}' if cast_image_path else "https://via.placeholder.com/500x500?text=No+Image"
                cast_members.append({
                    'name': cast_name,
                    'image_url': cast_image_url
                })

            return {
                'poster_url': poster_url,
                'title': title,
                'rating': rating,
                'release_date': release_date,
                'plot': plot,
                'director_name': director_name,
                'director_image_url': director_image_url,
                'cast_members': cast_members
            }

        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)  # Wait before retrying
                continue
            return {"error": f"Failed to fetch data: {str(e)}"}


# Recommendation system
def recommend(movie):
    try:
        movie_index = movies[movies['title'] == movie].index[0]
        distances = similarity[movie_index]
        movie_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]

        recommended_movies = []

        # Parallelize the API requests using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            movie_ids = [movies.iloc[i[0]].movie_id for i in movie_list]
            futures = [executor.submit(fetch_cached_movie_details, movie_id) for movie_id in movie_ids]

            for future in concurrent.futures.as_completed(futures):
                movie_details = future.result()
                if 'error' in movie_details:
                    recommended_movies.append({
                        "title": "Details not available", "poster_url": "", "rating": "", "release_date": "",
                        "plot": "", "director_name": "", "director_image_url": "", "cast_members": []
                    })
                else:
                    recommended_movies.append(movie_details)

        return recommended_movies
    except IndexError:
        return [{"title": "Movie not found", "poster_url": "", "rating": "", "release_date": "", "plot": "",
                 "director_name": "", "director_image_url": "", "cast_members": []}]


# Load movie data
movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

# Streamlit UI
st.title('Movie Recommender System')
selected_movie_name = st.selectbox('Find your next watch', movies['title'].values)

if st.button('Lets Goo'):
    recommended_movies = recommend(selected_movie_name)
    for movie in recommended_movies:
        st.write("---")
        st.header(movie['title'])

        if movie['poster_url']:
            st.image(movie['poster_url'], width=300)
        else:
            st.image("https://via.placeholder.com/500x750?text=Poster+Not+Found", width=300)

        st.write(f"*Rating:* {movie['rating']}/10")
        st.write(f"*Release Date:* {movie['release_date']}")
        st.write(f"*Plot:* {movie['plot']}")
        st.write(f"*Director:* {movie['director_name']}")

        if movie['director_image_url']:
            st.image(movie['director_image_url'], width=150, caption=f"Director: {movie['director_name']}")
        else:
            st.image("https://via.placeholder.com/500x500?text=No+Image", width=150)

        st.write("*Cast:*")
        cols = st.columns(3)
        for idx, cast_member in enumerate(movie['cast_members']):
            with cols[idx]:
                st.image(cast_member['image_url'] if cast_member[
                    'image_url'] else "https://via.placeholder.com/500x500?text=No+Image", width=150)
                st.caption(cast_member['name'])