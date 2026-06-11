# Árvore Genealógica — Família das Neves / Rossi

Projeto de organização da árvore genealógica de **Fabian Marcel das Neves Lima**,
com foco inicial no **lado materno (Rossi / das Neves)** para fins de
**reconhecimento de cidadania italiana** *jure sanguinis*.

## Linha de transmissão (lado materno)

```mermaid
flowchart TD
    GR["Giovanni Rossi"] --- MRDP["Maria Rosaria Del Principe"]
    DF["Domenico Fracassi"] --- GS["Giovanna Saltarelli"]
    GR & MRDP --> FR
    DF & GS --> PF

    FR["Francesco Luigi Rossi<br/>n. ~1835 — Pescasseroli<br/>pastor"] --- PF["Maria Pasquala Fracassi<br/>n. ~1836 — Pescasseroli<br/>casamento: 09/07/1859"]
    FR & PF --> NICOLA

    BS["Biagio Schettina"] --- MVO["Maria Vincenza Oliva"]
    BS & MVO --> MARIA

    NICOLA["🇮🇹 Nicola Giovanni Rossi<br/>n. 11/04/1867 — Pescasseroli (AQ), Itália<br/>f. 08/03/1943 — Rio de Janeiro"]
    MARIA["🇮🇹 Maria Schettina Rossi<br/>n. ~1865 — Itália<br/>f. 26/07/1946 — Rio de Janeiro"]
    NICOLA === MARIA
    NICOLA & MARIA --> NARCISA

    ARLINDO["Arlindo José das Neves"]
    NARCISA["Maria Narcisa Rossi das Neves"]
    ARLINDO === NARCISA
    ARLINDO & NARCISA --> FABIANO

    FABIANO["Fabiano Rossi das Neves<br/>n. 26/10/1941 — Rio de Janeiro<br/>advogado"]
    FABIANO --> FLAVIA

    FLAVIA["Flavia Cristina Aguiar das Neves"]
    FLAVIA --> FABIAN

    FABIAN["Fabian Marcel das Neves Lima<br/>(requerente)"]
```

## Estrutura do repositório

| Arquivo | Conteúdo |
|---|---|
| [`arvore.md`](arvore.md) | Fichas individuais de cada pessoa, com todos os dados extraídos dos documentos |
| [`cidadania-italiana.md`](cidadania-italiana.md) | Análise do caso, checklist de documentos e pendências |
| [`caca-documentos.md`](caca-documentos.md) | Guia prático para localizar cada documento faltante (cartórios, Arquivo Nacional, Portale Antenati, comune) |
| [`documentos/`](documentos/) | Cópias digitais dos documentos já obtidos |

## Resumo do caso

- **Dante causa:** Nicola Giovanni Rossi, nascido em Pescasseroli (L'Aquila, Abruzzo)
  em 11/04/1867 — certidão de nascimento italiana já obtida (atto n. 44).
- **Não naturalização confirmada:** duas certidões negativas do Ministério da Justiça
  (emitidas em 26/03/2026) atestam que Nicola nunca se naturalizou brasileiro.
- **Bônus:** a esposa, Maria Schettina, também era italiana — a linha é
  duplamente italiana na geração imigrante.
- **Geração de transmissão:** Nicola → Maria Narcisa Rossi das Neves (filha) →
  Fabiano Rossi das Neves (neto) → Flavia Cristina Aguiar das Neves (bisneta) →
  Fabian Marcel das Neves Lima (trineto).

> ⚠️ **Atenção:** ver [`cidadania-italiana.md`](cidadania-italiana.md) sobre a
> mudança na lei italiana de 2025 (Lei 74/2025), que impacta diretamente
> pedidos além da 2ª geração, e sobre divergências de nomes entre os documentos.
