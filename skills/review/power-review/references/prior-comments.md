# Subagente — comentários anteriores (anti-duplicação / reforço)

Use **somente no modo MR**. Delega a um subagente (`Task`, `generalPurpose`) para
não poluir o contexto do orquestrador.

## Objetivo

Dado o MR e a lista preliminar de achados novos, classificar cada um como:

| Classe | Ação |
|---|---|
| `NOVO` | Publicar normalmente (template completo) |
| `DUPLICADO` | **Omitir** publicação — já coberto por thread/note anterior |
| `REFORÇO` | Publicar só se o problema **ainda existe** no código atual; corpo curto apontando o thread anterior |

## Coleta (subagente ou orquestrador)

```bash
glab api "projects/:id/merge_requests/<IID>/discussions"
glab api "projects/:id/merge_requests/<IID>/notes"
```

Incluir: body, autor, path/line (se discussion com position), created_at, id/url do thread.

Ignorar a própria nota-resumo com marcador `<!-- power-review:head_sha=` para fins de “tema do achado” (ela é índice, não thread de achado). Considerar discussions inline e notes humanas/bot de review.

## Prompt do subagente

```
Classifique achados de code review contra comentários já existentes no MR <IID>.
NÃO invente novos achados. NÃO publique nada.

### Comentários / discussions existentes
<cole aqui: path, linha, trecho do body, id/url, data>

### Achados candidatos (deste review)
<lista: severidade, path, new_line, título, resumo do problema>

Para cada candidato, retorne SOMENTE markdown:

## Prior comments — MR <IID>
| # | Título | Classe | Thread prévio | Motivo |
|---|---|---|---|---|
| 1 | ... | NOVO\|DUPLICADO\|REFORÇO | <url/id ou —> | <1 linha> |

### Reforços a publicar
Para cada REFORÇO (problema ainda presente), rascunho curto:

**[REFORÇO — <tema>] — <título>**
- Ainda presente em `<path>:<line>`
- Thread anterior: <url>
- Evidência: <1-2 frases>
- (opcional) Antes/Depois só se o fix sugerido mudou

### Omitidos (DUPLICADO)
- <título> — já em <url>
```

## Regras de classificação

- Mesmo arquivo + mesmo tema/problema (mesmo que linhas tenham mudado) → `DUPLICADO` se o thread ainda descreve o estado atual, ou `REFORÇO` se o código ainda viola e vale insistir.
- Problema novo ou ângulo materialmente diferente → `NOVO`.
- Se o thread antigo foi resolvido (código corrigido) e o candidato é outro assunto → `NOVO`.
- Na dúvida entre DUPLICADO e REFORÇO: preferir **REFORÇO** só quando a severidade for CRÍTICO/ALTO e o bug ainda for reproduzível; senão DUPLICADO.

## Uso pelo orquestrador

1. Filtrar a lista final: publicar só `NOVO` + `REFORÇO` aprovados.
2. Na nota-resumo: mencionar quantos foram omitidos por duplicação e quantos reforçados.
3. Achados `REFORÇO` podem usar template reduzido (sem Ante/Depois longos), mas ainda em pt-br.
