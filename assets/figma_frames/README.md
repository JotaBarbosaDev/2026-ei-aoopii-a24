# Figma Frames

Esta pasta guarda as overlays PNG exportadas do Figma que o pipeline aplica por cima das imagens geradas.

## Ficheiros esperados

- `frame_1600x896.png`
- `frame_1200x632.png`

Tambem podes usar caminhos custom na `.env`:

- `FIGMA_FRAME_PATH_1600x896=assets/figma_frames/frame_1600x896.png`
- `FIGMA_FRAME_PATH_1200x632=assets/figma_frames/frame_1200x632.png`

## Como preparar no Figma

1. Cria uma frame com tamanho `1600x896`.
2. Cria outra frame com tamanho `1200x632`.
3. Em cada frame, deixa apenas os elementos de branding que devem ficar por cima da imagem:
   - logo
   - moldura
   - barras
   - cantos
   - elementos decorativos
4. O fundo da frame deve ficar transparente.
5. Nao coloques a imagem de conteudo dentro da frame. O bot gera essa imagem e depois aplica a overlay.
6. Exporta cada frame como `PNG`.
7. Guarda os ficheiros nesta pasta com estes nomes exatos:
   - `frame_1600x896.png`
   - `frame_1200x632.png`

## Como o bot usa estas frames

- `blog` e `twitter` usam `1600x896`
- `linkedin` e `newsletter` usam `1200x632`

Se estes PNGs existirem, o bot usa-os primeiro e nao depende da API do Figma em runtime.
