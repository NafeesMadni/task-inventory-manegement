# import pytest
# from httpx import AsyncClient


# @pytest.mark.asyncio
# async def test_get_available_devices(client: AsyncClient):
#     headers = {"access_token": "Bearer YOUR_ACCESS_TOKEN_HERE"}

#     response = await client.get("/device/available", headers=headers)

#     assert response.status_code == 200

#     assert isinstance(response.json(), list)
