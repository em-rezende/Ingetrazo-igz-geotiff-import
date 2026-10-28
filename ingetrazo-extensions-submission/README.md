# Submissão ao catálogo de extensões do IngeTrazo

Estes dois arquivos são o que se copia para
<https://github.com/ingelibre/ingetrazo-extensions> (pull request):

| Arquivo local | Destino no catálogo |
| :--- | :--- |
| `extensions/igz_geotiff_import.toml` | `extensions/igz_geotiff_import.toml` |
| `screenshots/igz_geotiff_import.png` | `screenshots/igz_geotiff_import.png` |

A ficha aponta para o asset da release **v1.0.0**
(`igz_geotiff_import.zip`) e fixa o `sha256`
`7894ae4d0d01c995ef7572333680b481112deda2cb402671ab42971496355939`.

Validação local (dentro do clone do catálogo):

```text
python tools/catalog.py check igz_geotiff_import
```

O robô do catálogo lê o código (não executa) e confere: campos completos,
licença livre, `download` preso a uma tag, huella correta e a presença de
`setup(app)`/`Tool` no pacote. Depois um mantenedor aprova a pull request.

Ao publicar uma versão nova: atualizar `version`, `download` e `sha256` aqui
e abrir outra pull request (vinda da conta `em-rezende`, ela se publica
sozinha como «Comunidade»).
