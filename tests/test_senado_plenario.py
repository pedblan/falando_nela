from __future__ import annotations

import httpx

from coleta.common.http import OpenDataClient
from coleta.senado.plenario_discursos.collect import (
    build_pronunciamento_payload,
    extract_pronunciamentos,
    fetch_pronunciamento_texto,
    should_enqueue_transcription,
)


def test_extract_pronunciamentos_combines_session_and_speech_metadata() -> None:
    payload = {
        "DiscursosSessao": {
            "Sessoes": {
                "Sessao": {
                    "CodigoSessao": "21014",
                    "DataSessao": "2011-05-31",
                    "Pronunciamentos": {
                        "Pronunciamento": {
                            "CodigoPronunciamento": "389577",
                            "NomeAutor": "Autor",
                            "TextoIntegralTxt": "https://example.test/texto/389577",
                            "TextoIntegral": "https://example.test/html/389577",
                            "UrlTextoBinario": "https://example.test/bin/389577",
                        }
                    },
                }
            }
        }
    }

    items = extract_pronunciamentos(payload)

    assert len(items) == 1
    item = items[0]
    assert item["codigo_pronunciamento"] == "389577"
    assert item["metadata"]["sessao"] == {"CodigoSessao": "21014", "DataSessao": "2011-05-31"}
    assert item["metadata"]["pronunciamento"]["NomeAutor"] == "Autor"
    assert item["fontes"]["texto_integral_txt"] == "https://example.test/texto/389577"
    assert item["fontes"]["notas_sessao_api"].endswith("/dadosabertos/taquigrafia/notas/sessao/21014.json")
    assert item["fontes"]["videos_sessao_api"].endswith("/dadosabertos/taquigrafia/videos/sessao/21014")


def test_build_pronunciamento_payload_text_contract() -> None:
    item = {
        "codigo_pronunciamento": "389577",
        "metadata": {"sessao": {}, "pronunciamento": {}},
        "fontes": {"texto_integral_txt": "https://example.test/texto/389577"},
    }

    payload = build_pronunciamento_payload(
        item,
        texto="texto integral",
        forma="texto",
        metodo_obtencao="api_texto_integral",
        texto_status="disponivel",
    )

    assert payload["codigo_pronunciamento"] == "389577"
    assert payload["CodigoPronunciamento"] == "389577"
    assert payload["texto"] == "texto integral"
    assert payload["TextoIntegral"] == "texto integral"
    assert payload["TextoIntegralUrl"] == "https://example.test/texto/389577"
    assert payload["forma"] == "texto"
    assert payload["metodo_obtencao"] == "api_texto_integral"
    assert payload["texto_status"] == "disponivel"
    assert not should_enqueue_transcription(payload)


def test_pending_video_payload_enters_transcription_queue() -> None:
    item = {
        "codigo_pronunciamento": "389577",
        "metadata": {"sessao": {}, "pronunciamento": {}},
        "fontes": {
            "texto_integral_txt": "https://example.test/texto/389577",
            "texto_binario": "https://example.test/bin/389577",
            "videos_sessao_api": "https://example.test/videos/1",
        },
    }

    payload = build_pronunciamento_payload(
        item,
        texto=None,
        forma="video",
        metodo_obtencao="pendente_transcricao_video",
        texto_status="erro",
    )

    assert payload["texto"] is None
    assert payload["TextoIntegral"] is None
    assert payload["forma"] == "video"
    assert payload["metodo_obtencao"] == "pendente_transcricao_video"
    assert should_enqueue_transcription(payload)


def test_fetch_pronunciamento_texto_falls_back_to_session_notes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.test/dadosabertos/discurso/texto-integral/389577":
            return httpx.Response(404, json={"status": 404})
        if str(request.url) == "https://example.test/notas/21014":
            return httpx.Response(200, json={"Notas": {"Texto": "texto da sessao"}})
        return httpx.Response(500)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    item = {
        "codigo_pronunciamento": "389577",
        "metadata": {"sessao": {}, "pronunciamento": {}},
        "fontes": {
            "texto_integral_txt": "https://example.test/metadata-link-not-used/389577",
            "notas_sessao_api": "https://example.test/notas/21014",
            "texto_binario": "https://example.test/bin/389577",
        },
    }

    payload, request, response = fetch_pronunciamento_texto(client, item)

    assert payload["texto"] == "texto da sessao"
    assert payload["TextoIntegral"] == "texto da sessao"
    assert payload["forma"] == "texto"
    assert payload["metodo_obtencao"] == "api_notas_sessao"
    assert payload["texto_status"] == "disponivel"
    assert payload["tentativas_texto"][0]["metodo_obtencao"] == "api_texto_integral"
    assert request["path"] == "https://example.test/notas/21014"
    assert response["status_code"] == 200
    assert not should_enqueue_transcription(payload)


def test_fetch_pronunciamento_texto_queues_video_after_text_and_session_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"status": 404})

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    item = {
        "codigo_pronunciamento": "389577",
        "metadata": {"sessao": {}, "pronunciamento": {}},
        "fontes": {
            "texto_integral_txt": "https://example.test/metadata-link-not-used/389577",
            "notas_sessao_api": "https://example.test/notas/21014",
            "videos_sessao_api": "https://example.test/videos/21014",
        },
    }

    payload, request, response = fetch_pronunciamento_texto(client, item)

    assert payload["texto"] is None
    assert payload["TextoIntegral"] is None
    assert payload["forma"] == "video"
    assert payload["metodo_obtencao"] == "pendente_transcricao_video"
    assert payload["texto_status"] == "erro"
    assert [item["metodo_obtencao"] for item in payload["tentativas_texto"]] == [
        "api_texto_integral",
        "api_notas_sessao",
    ]
    assert request["path"] == "dadosabertos/discurso/texto-integral/389577"
    assert response["status_code"] == 404
    assert should_enqueue_transcription(payload)


def test_fetch_pronunciamento_texto_stores_response_body_not_link() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text="texto de fato")

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    item = {
        "codigo_pronunciamento": "389577",
        "metadata": {"sessao": {}, "pronunciamento": {}},
        "fontes": {
            "texto_integral_txt": "https://example.test/metadata-link-not-used/389577",
        },
    }

    payload, request, response = fetch_pronunciamento_texto(client, item)

    assert requested_urls == ["https://example.test/dadosabertos/discurso/texto-integral/389577"]
    assert request["path"] == "dadosabertos/discurso/texto-integral/389577"
    assert response["status_code"] == 200
    assert payload["texto"] == "texto de fato"
    assert payload["TextoIntegral"] == "texto de fato"
    assert payload["TextoIntegralUrl"] == "https://example.test/metadata-link-not-used/389577"
    assert payload["texto"] != item["fontes"]["texto_integral_txt"]
    assert payload["TextoIntegral"] != item["fontes"]["texto_integral_txt"]
    assert payload["metodo_obtencao"] == "api_texto_integral"
