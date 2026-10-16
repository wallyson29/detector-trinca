
---

## 📄 Arquivo 2: `DECISIONS.md`

```markdown
# Decisões Técnicas

Documento com o **porquê** de cada escolha técnica. Se um dia alguém questionar "por que isso tá assim?", a resposta está aqui.

---

## 🔍 Verificação de qualidade de foto

### Decisão
Bloquear fotos com **nitidez < 15** OU (nitidez < 15 E densidade de bordas < 0.7%) + brilho fora do intervalo 100-220 + resolução < 800x600.

### Por quê
Testamos 4 fotos reais:
- Foto boa de câmera de celular: nitidez 18, bordas 1.17%
- Foto boa de upload (galeria): nitidez 66
- Foto tremida de propósito: nitidez 14, bordas 0.00%
- Foto escura (lente tampada): nitidez 11, bordas 0.00%

**Problema inicial:** o limiar 100 (padrão da indústria pra fotos gerais) bloqueava fotos boas de câmera de celular. Isso acontece porque o Laplaciano mede variância pixel a pixel, e câmera de celular tem muito ruído de ISO, o que dilui a métrica.

**Solução:** combinamos 2 métricas — nitidez (Laplaciano) + densidade de bordas (Canny). A foto passa se **pelo menos uma** estiver OK. Assim aceitamos tanto câmera quanto upload.

### Trade-offs
- Foto muito borrada passa? **Não** — testado, tremida dá nitidez 14 e bordas 0%.
- Foto escura passa? **Não** — brilho fora do intervalo bloqueia.
- Risco: foto de superfície muito lisa (chapa sem textura) pode dar nitidez e bordas baixas mesmo focada. Mas no nosso caso sempre tem parafuso, trinca ou solda, então não é problema.

---

## 🧠 Análise por peça (não em lote)

### Decisão
Analisar 1 peça por vez, com 2 imagens cada (original + CLAHE), em vez de mandar as 9 fotos de uma vez.

### Por quê
Testamos inicialmente com **todas as fotos em uma única chamada**. Resultado:
- A IA perdia atenção
- Não detectava trincas finas
- Misturava informações entre peças

Quando mudamos pra **1 peça por vez**, a IA:
- Focou 100% naquela imagem
- Detectou mais trincas
- Deu laudo individual por peça (rastreável)

### Trade-offs
- **Mais lento** (~30s no total vs ~10s com lote)
- **Mais chamadas de API** (8 chamadas vs 1)
- **Vale a pena** pela precisão e rastreabilidade

---

## 🖼️ CLAHE + imagem original (2 imagens por análise)

### Decisão
Para cada peça, mandar **2 imagens** pro Gemini: a original em cores + a versão com CLAHE (realce de contraste em tons de cinza).

### Por quê
- A **original** mostra cor real do metal, ferrugem, tonalidades
- O **CLAHE** realça detalhes finos que a cor esconde (trincas finas em metal)
- O Gemini **junta as duas** e decide com mais informação

### Trade-offs
- Custa mais tokens (2 imagens por peça)
- Mas a detecção é melhor

---

## 📸 9 fotos obrigatórias

### Decisão
Checklist fixo com 9 fotos: 8 peças técnicas + foto da placa.

### Por quê
O técnico do cliente descreveu exatamente essa lista como o checklist padrão da inspeção dele. É o que a empresa exige.

### Trade-offs
- Rígido: se a empresa mudar o checklist, precisa mexer no código
- Mitigação: a lista está em `config.py` — fácil de alterar

---

## 🔒 Bloqueio de 15 dias entre análises

### Decisão
Não permitir nova análise da mesma placa em menos de 15 dias. Admin pode forçar (flag `forcado = true` no banco).

### Por quê
Regra de negócio do cliente. Evita:
- Análise duplicada sem motivo
- Gasto de API desnecessário
- Sobrecarga do técnico

Mas o admin precisa poder forçar em caso de:
- Suspeita específica
- Reincidência
- Auditoria externa

### Trade-offs
- 15 dias é parâmetro fixo em `config.py`
- Poderia ser por peça em vez de por placa, mas decidimos que "a inspeção é do caminhão inteiro, não de peça isolada"

---

## 🗄️ Supabase em vez de banco próprio

### Decisão
Usar Supabase (PostgreSQL gerenciado) em vez de Postgres em VPS ou AWS RDS.

### Por quê
- **Setup em minutos** vs dias
- **Auth incluso** (não precisa implementar JWT)
- **Storage incluso** (não precisa S3)
- **RLS nativo** (segurança em nível de linha)
- **Free tier generoso** (500 MB + 1 GB storage)
- **Backup automático** no plano Pro

### Trade-offs
- Vendor lock-in (difícil migrar depois)
- Limite de 500 MB no free tier (~2 meses com 9 fotos/análise)
- Alternativa: PostgreSQL próprio + S3 + Auth0 = mais trabalho inicial

---

## 🔐 RLS (Row Level Security) em vez de middleware

### Decisão
Configurar RLS **no banco** em vez de validar permissões no código Python.

### Por quê
- **Segurança em profundidade**: mesmo se o código Python tiver falha, o banco protege
- **Menos código**: sem `if user.role == 'admin'` espalhado pelo app
- **Padrão da indústria**: Supabase é feito pra isso

### Trade-offs
- Mais difícil de debugar (erro de RLS retorna vazio, não erro explícito)
- Precisa de `SECURITY DEFINER` em algumas funções RPC pra contornar

---

## 🎨 Streamlit em vez de React/Next.js

### Decisão
Usar Streamlit (framework Python) em vez de fazer frontend em React/Next.js.

### Por quê
- **Setup em horas** vs semanas
- **Tudo em Python** (mesma linguagem do backend)
- **Deploy grátis** no Streamlit Cloud
- **Fácil iterar** — código direto no app

### Trade-offs
- Não é nativo mobile (funciona, mas não perfeito)
- Menos flexível visualmente
- State management é meio limitado (session_state)
- **Vale a pena pro MVP**. Se crescer muito, migrar pra Next.js.

---

## 🤖 Gemini 3.5 Flash Lite em vez de GPT-4 Vision

### Decisão
Usar Google Gemini 3.5 Flash Lite como modelo de visão.

### Por quê
- **Preço**: muito mais barato que GPT-4 Vision
- **Free tier**: ~1500 req/dia gratuito
- **Visão de qualidade**: suficiente pro nosso caso
- **API simples**: chamada direta com `client.models.generate_content`

### Trade-offs
- **Instabilidade**: erros 503 (sobrecarga) acontecem, por isso o retry automático
- **Menos preciso** que GPT-4 Vision em casos limítrofes
- **Alternativas** se precisar: DeepSeek Vision (mais barato), GPT-4o Vision (mais preciso)

---

## 🔄 Retry automático (3 tentativas)

### Decisão
Se o Gemini der erro 503 (sobrecarga) ou 429 (rate limit), tentar de novo até 3 vezes, com 5s entre tentativas.

### Por quê
O Gemini 3.5 Flash Lite tá em alta demanda. 503 é frequente e **temporário**. Sem retry, o laudo vem incompleto. Com retry, 90% dos casos resolvem.

### Trade-offs
- Mais lento em caso de erro (15s a mais)
- Mas evita laudo incompleto, que é pior

---

## 🚫 Bloqueio de laudo se peça der erro

### Decisão
Se após 3 tentativas de retry uma peça continuar dando erro, **bloquear o laudo** (não salva no banco). Dar opção de **reanalisar só as peças com erro**.

### Por quê
Laudo com peça não analisada é **perigoso**. O técnico precisa saber que **tudo** foi inspecionado. Senão, pode liberar caminhão com trinca não detectada.

### Trade-offs
- Técnico fica travado se o Gemini estiver caído
- Mitigação: botão "cancelar análise" pra recomeçar do zero
- Alternativa rejeitada: salvar com aviso — abre brecha pra técnico liberar caminhão com laudo incompleto

---

## 📝 Observação sem IA

### Decisão
O campo de observação (foto extra + texto) é **só registrado**, não passa pela IA.

### Por quê
A observação é livre — o técnico pode anotar "para-lama amassado", "parafuso faltando", "vazamento de óleo", etc. Não é necessariamente uma peça do checklist.

### Trade-offs
- Observação fica no PDF mas não gera status estruturado
- **Vale a pena** pela simplicidade

---

## 🖼️ Foto da placa não vai pra IA

### Decisão
A foto 9 (placa do caminhão) é obrigatória, mas **não é analisada** pela IA.

### Por quê
Só serve pra registrar visualmente a placa. Não tem estrutura pra analisar trinca.

### Trade-offs
- Nenhum. É só registro mesmo.

---

## 🎯 Limiares de qualidade calibrados com fotos reais

### Decisão
Os limiares (`LIMIAR_NITIDEZ = 15`, `LIMIAR_DENSIDADE_BORDAS = 0.7`) foram calibrados com fotos do cliente, não com padrões genéricos.

### Por quê
Limiares padrão da indústria (nitidez 100+) bloqueiam fotos boas de câmera de celular. Fotos do técnico no pátio têm:
- Alta resolução (3000x4000+)
- Ruído de ISO
- Iluminação variável (sol, sombra, garagem)

Cada contexto é diferente. Os limiares precisam ser **calibrados pro caso real**.

### Como recalibrar (se mudar de celular)
1. Tira 1 foto boa de câmera
2. Tira 1 foto tremida (chacoalha)
3. Sobe no app
4. Anota os valores de nitidez e bordas
5. Ajusta `LIMIAR_NITIDEZ` e `LIMIAR_DENSIDADE_BORDAS` no `config.py`

**Regra de ouro:** foto boa passa **com folga**, foto ruim falha **com folga**. Os limiares ficam **no meio**, não no limite.

---

## 🧾 Exibição de horário

### Decisão
Guardar datas no banco em **UTC** (padrão Supabase) e exibir no app em **UTC** também.

### Por quê
- UTC é o padrão da indústria
- Conversão pra Brasília pode ser adicionada depois
- Evita bugs de timezone

### Trade-offs
- Usuário pode estranhar o horário 3h adiantado
- Mitigação futura: formatar com `ZoneInfo("America/Sao_Paulo")` na exibição

---

## 💾 Sem backup automático (free tier)

### Decisão
Usar o free tier do Supabase sem backup automático.

### Por quê
MVP com 1 cliente piloto. Backup manual (exportar SQL 1x por semana) é suficiente.

### Riscos
- Se o Supabase tiver falha catastrófica, perde tudo desde o último backup manual
- **Quando escalar:** ativar plano Pro (US$ 25/mês) com backup diário

### Mitigação
- Exportar SQL semanalmente
- Guardar em Drive/pen drive
- Documentar processo de restore

---

## 📅 Roadmap futuro (ideias, não compromissos)

- [ ] PDF com assinatura digital
- [ ] Exportação em lote (várias análises de uma vez)
- [ ] Integração com sistema da transportadora (via API)
- [ ] App mobile nativo (PWA ou React Native)
- [ ] Detecção de outros tipos de defeito (amassado, vazamento)
- [ ] Comparação automática entre análises (evolução da peça)
- [ ] Notificação por email/WhatsApp quando detectar trinca severa
- [ ] Multi-idioma (espanhol pro Mercosul)

---

**Última atualização:** 16/10/2026
