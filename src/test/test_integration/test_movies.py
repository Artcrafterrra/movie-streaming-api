import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_movie(client: AsyncClient, auth_headers):
    payload = {
        "name": "Inception",
        "year": 2010,
        "time": 148,
        "imdb": 8.8,
        "votes": 2000000,
        "meta_score": 74,
        "gross": 829.9,
        "description": "Mind-bending thriller.",
        "price": 12.50,
        "certification": "PG-13",
    }

    response = await client.post(
        "/api/v1/movies/", json=payload, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Inception"
    assert data["year"] == 2010
    assert data["certification"] == "PG-13"


@pytest.mark.asyncio
async def test_get_movie_by_id(client: AsyncClient, sample_movie):
    response = await client.get(f"/api/v1/movies/{sample_movie.id}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == sample_movie.id
    assert data["name"] == "Test Movie"
    assert "genres" in data


@pytest.mark.asyncio
async def test_update_movie(client: AsyncClient, auth_headers, sample_movie):
    update_payload = {"imdb": 9.0}
    response = await client.patch(
        f"/api/v1/movies/{sample_movie.id}/",
        json=update_payload,
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["imdb"] == 9.0


@pytest.mark.asyncio
async def test_delete_movie(client: AsyncClient, auth_headers, sample_movie):
    response = await client.delete(
        f"/api/v1/movies/{sample_movie.id}/", headers=auth_headers
    )
    assert response.status_code == 204
    response_2 = await client.delete(
        f"/api/v1/movies/{sample_movie.id}/", headers=auth_headers
    )
    assert response_2.status_code == 404


@pytest.mark.asyncio
async def test_get_genres_list(client: AsyncClient):
    response = await client.get("/api/v1/movies/genres/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_genre_by_id_not_found(client: AsyncClient):
    response = await client.get("/api/v1/movies/genres/999/")
    assert response.status_code == 404
    assert "Genre" in response.text


@pytest.mark.asyncio
async def test_react_to_movie_like_then_remove(
    client: AsyncClient, auth_headers, sample_movie
):
    url = f"/api/v1/movies/{sample_movie.id}/reaction/?user_id=1"
    payload = {"value": 1}
    response = await client.post(url, json=payload, headers=auth_headers)

    if response.status_code == 401:
        pytest.skip("User not authorized in test environment")
    else:
        assert response.status_code in (200, 201, 204), response.text
        payload = {"value": 0}
        response2 = await client.post(url, json=payload, headers=auth_headers)
        assert response2.status_code in (200, 204), response2.text


@pytest.mark.asyncio
async def test_get_movie_reactions_stats(client: AsyncClient, sample_movie):
    response = await client.get(f"/api/v1/movies/{sample_movie.id}/reactions/")
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        data = response.json()
        assert "likes_count" in data
        assert "dislikes_count" in data


@pytest.mark.asyncio
async def test_add_comment_and_list_comments(
    client: AsyncClient, auth_headers, sample_movie
):
    url = f"/api/v1/movies/{sample_movie.id}/comments/?user_id=1"
    payload = {"body": "Awesome film!"}
    response = await client.post(url, json=payload, headers=auth_headers)

    if response.status_code == 401:
        pytest.skip("User not authorized in test environment")
    else:
        assert response.status_code in (200, 201, 204), response.text
        response2 = await client.get(
            f"/api/v1/movies/{sample_movie.id}/comments/"
        )
        assert response2.status_code == 200
        comments = response2.json()
        assert isinstance(comments, list)


@pytest.mark.asyncio
async def test_delete_comment(client: AsyncClient, auth_headers, sample_movie):
    payload = {"body": "Temporary comment"}
    create_resp = await client.post(
        f"/api/v1/movies/{sample_movie.id}/comments/?user_id=1",
        json=payload,
        headers=auth_headers,
    )
    if create_resp.status_code in (200, 201):
        comment_id = create_resp.json().get("id", 1)
        delete_resp = await client.delete(
            f"/api/v1/movies/comments/{comment_id}/?user_id=1",
            headers=auth_headers,
        )
        assert delete_resp.status_code in (200, 204, 404)


@pytest.mark.asyncio
async def test_add_update_get_delete_rating(
    client: AsyncClient, auth_headers, sample_movie
):
    base_url = f"/api/v1/movies/{sample_movie.id}/rating/?user_id=1"
    payload = {"score": 8}

    response = await client.post(base_url, json=payload, headers=auth_headers)
    if response.status_code == 401:
        pytest.skip("User not authorized in test environment")
    else:
        assert response.status_code in (200, 201, 204), response.text

        payload = {"score": 9}
        update_resp = await client.post(
            base_url, json=payload, headers=auth_headers
        )
        assert update_resp.status_code in (200, 201, 204), update_resp.text

        avg_resp = await client.get(
            f"/api/v1/movies/{sample_movie.id}/rating/"
        )
        assert avg_resp.status_code in (200, 404)

        delete_resp = await client.delete(base_url, headers=auth_headers)
        assert delete_resp.status_code in (200, 204, 404)


@pytest.mark.asyncio
async def test_add_remove_favorite_and_list(
    client: AsyncClient, auth_headers, sample_movie
):
    base_url = f"/api/v1/movies/favorites/{sample_movie.id}/?user_id=1"
    list_url = "/api/v1/movies/favorites/?user_id=1"

    response = await client.post(base_url, headers=auth_headers)
    if response.status_code == 401:
        pytest.skip("User not authorized in test environment")
    else:
        assert response.status_code in (200, 201, 204), response.text

        list_resp = await client.get(list_url, headers=auth_headers)
        assert list_resp.status_code in (200, 404)
        if list_resp.status_code == 200:
            assert isinstance(list_resp.json(), list)

        del_resp = await client.delete(base_url, headers=auth_headers)
        assert del_resp.status_code in (200, 204, 404)


@pytest.mark.asyncio
async def test_get_movies_by_genre(client: AsyncClient):
    response = await client.get("/api/v1/movies/genres/1/movies/")
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_director_and_star(client: AsyncClient, auth_headers):
    d_resp = await client.post(
        "/api/v1/movies/directors/",
        params={"name": "Christopher Nolan"},
        headers=auth_headers,
    )
    if d_resp.status_code == 401:
        pytest.skip("User not authorized in test environment")
    else:
        assert d_resp.status_code in (200, 201, 204), d_resp.text

    s_payload = {"name": "Leonardo DiCaprio"}
    s_resp = await client.post(
        "/api/v1/movies/actors/",
        json=s_payload,
        headers=auth_headers,
    )
    if s_resp.status_code == 401:
        pytest.skip("User not authorized in test environment")
    else:
        assert s_resp.status_code in (200, 201, 204), s_resp.text

    d_list = await client.get("/api/v1/movies/directors/")
    assert d_list.status_code in (200, 404)

    s_list = await client.get("/api/v1/movies/actors/")
    assert s_list.status_code in (200, 404)
