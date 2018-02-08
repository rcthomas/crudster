
import sys
from urllib.parse import urljoin

import pytest
from tornado.escape import json_encode, json_decode
from tornado.httpclient import HTTPError

from crudster import create_crudster

@pytest.fixture
def app():
    crud = create_crudster(initialize_database=True)
    crud.listen(8888)
    return crud

@pytest.fixture
def base_url():
    return "http://localhost:8888"

@pytest.mark.gen_test
def test_get(http_client, base_url):
    response = yield http_client.fetch(base_url)
    assert response.code == 200

    response_doc = json_decode(response.body)
    assert len(response_doc) == 0

@pytest.mark.gen_test
def test_crud(http_client, base_url):

    doc = dict(Hello="Doctor", Name="Continue", Yesterday="Tomorrow")

    # Create, should get a response document with UUID

    c_response = yield http_client.fetch(base_url, method="POST", body=json_encode(doc))
    assert c_response.code == 200

    c_response_doc = json_decode(c_response.body)
    assert "uuid" in c_response_doc

    # Read, should get document back

    r_response = yield http_client.fetch(urljoin(base_url, c_response_doc["uuid"]))
    assert r_response.code == 200

    r_response_doc = json_decode(r_response.body)
    for key, value in doc.items():
        assert key in r_response_doc
        assert r_response_doc[key] == doc[key]

    # Update, actually replace the document if we want

    new_doc = dict(Computer="Science", Is="No", More="About", Computers="Than",
            Astronomy="Is", About="Telescopes")

    u_response = yield http_client.fetch(urljoin(base_url, c_response_doc["uuid"]), method="PUT", body=json_encode(new_doc))
    assert u_response.code == 200

    # Read, should get new document back

    r_response = yield http_client.fetch(urljoin(base_url, c_response_doc["uuid"]))
    assert r_response.code == 200

    r_response_doc = json_decode(r_response.body)
    for key, value in new_doc.items():
        assert key in r_response_doc
        assert r_response_doc[key] == new_doc[key]

    # Delete, document should go away

    u_response = yield http_client.fetch(urljoin(base_url, c_response_doc["uuid"]), method="DELETE")
    assert r_response.code == 200

    # Read, this should raise exception for a 404 not found error

    with pytest.raises(HTTPError) as exc:
        r_response = yield http_client.fetch(urljoin(base_url, c_response_doc["uuid"]))
    assert exc.value.code == 404
