from helpers import new_session


async def test_multipart_upload_reaches_the_service(authed):
    sid = await new_session(authed)
    r = await authed.post(
        f"/v1/sessions/{sid}/attachments",
        files=[("files", ("hello.txt", b"hello world", "text/plain"))],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body[0]["name"] == "hello.txt"
    assert body[0]["kind"] == "text"


async def test_upload_without_files_is_a_validation_error(authed):
    sid = await new_session(authed)
    r = await authed.post(f"/v1/sessions/{sid}/attachments", data={"x": "1"})
    assert r.status_code == 422
