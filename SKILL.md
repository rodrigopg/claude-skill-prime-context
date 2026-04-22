---
name: prime-context
description: Carrega contexto on demand ou refatora/configura estrutura de contexto de projetos. Comandos: load (padrão), improve, setup.
---

# Prime Context

Skill para gerenciar contexto de projetos de forma eficiente — sem carregar tudo de uma vez.

## Filosofia central

**AGENTS.md deve ser fino.** Ele é carregado em TODA sessão — cada linha desperdiça tokens.
O conteúdo detalhado vai em `.claude/context/<área>.md` e é lido **só quando a tarefa exige**.
AGENTS.md contém apenas: visão geral (2 linhas), tabela de roteamento, regras inegociáveis, checklist de PR.

---

## Comando: `load` (padrão quando sem argumento ou com nome de área)

Carrega contexto do projeto atual on demand.

**Fluxo:**
1. Leia o `MEMORY.md` do projeto em `~/.claude/projects/<hash>/memory/MEMORY.md`
2. Leia todos os arquivos listados no MEMORY.md
3. Se argumento for uma área (ex: `filament`, `api`, `prod`), leia o `.claude/context/<área>.md` correspondente
4. Sem argumento: leia `AGENTS.md` e apresente resumo do contexto

**Formato de saída:**
```
## Contexto carregado — <área ou "geral">

### O que é relevante agora
<3-5 pontos críticos para a sessão>

### Armadilhas conhecidas
<Learnings de memory aplicáveis>

### Referência rápida
<Comandos ou configs mais usados>
```

---

## Comando: `improve`

**Objetivo:** Pega um AGENTS.md gordo (qualquer projeto) e o refatora para a arquitetura thin + context files.

**Fluxo:**

1. Leia o `AGENTS.md` (ou `CLAUDE.md`) do CWD inteiro
2. Analise o conteúdo e identifique agrupamentos naturais por área (ex: Filament, PSA, API, DB, prod, multi-tenancy)
3. Para cada área identificada, crie `.claude/context/<área>.md` com o conteúdo detalhado daquela área
4. Reescreva o `AGENTS.md` seguindo o **template thin** abaixo
5. Verifique que `CLAUDE.md` é symlink para `AGENTS.md` — se não for, crie o symlink

**Template thin do AGENTS.md:**
```markdown
# <Nome do Projeto>

<Descrição de 1-2 linhas: o que faz, stack principal>

## Carregar contexto antes de trabalhar

Antes de iniciar qualquer tarefa, leia o arquivo de contexto correspondente:

| Área | Arquivo |
|------|---------|
| <área 1> | `.claude/context/<area1>.md` |
| <área 2> | `.claude/context/<area2>.md` |
...

Se a tarefa tocar múltiplas áreas, leia os arquivos relevantes em paralelo.

## Regras inegociáveis (sempre aplicar)

<Apenas as regras que se aplicam a TODA tarefa — máximo 8 bullets concisos>

## Checklist antes de abrir PR

<Checklist completo — este sempre é útil manter aqui>

## Comandos essenciais

<Apenas os comandos mais usados no dia a dia>

<Qualquer bloco auto-gerenciado por MCP/ferramentas vai ao final, sem tocar>
```

**Regras do improve:**
- Não inventar conteúdo — só reorganizar o que já existe no AGENTS.md original
- Blocos auto-gerenciados (`<laravel-boost-guidelines>`, `## graphify`, etc.) vão ao final do AGENTS.md intactos
- Se `.claude/context/` já tiver arquivos, mesclar com o conteúdo novo (não sobrescrever cegamente)
- Cada arquivo de context deve ter cabeçalho `# Contexto: <Área>` e ser autocontido
- Após criar os arquivos, informe: quantas linhas o AGENTS.md tinha antes e depois

---

## Comando: `setup`

**Objetivo:** Configura do zero a estrutura de contexto em um novo projeto.

**Fluxo:**

1. Use o CWD como raiz do projeto (ou pergunte se ambíguo)
2. Pergunte: "Descreva o projeto em 1-2 linhas (o que faz, stack, para quem)"
3. Pergunte: "Quais são as principais áreas de trabalho? (ex: API, banco, infra, frontend)" — sugerir baseado no stack detectado
4. Crie `.claude/context/<área>.md` vazio para cada área com header `# Contexto: <Área>\n\n<!-- Preencha conforme o projeto evoluir -->`
5. Crie `AGENTS.md` seguindo o template thin (com tabela de roteamento para as áreas criadas)
6. Crie symlink `CLAUDE.md → AGENTS.md` (se CLAUDE.md não existir)
7. Crie `~/.claude/projects/<hash>/memory/MEMORY.md` vazio com instrução de formato

**Hash do projeto:** substitua `/` por `-` no path absoluto do projeto (mesmo padrão do Claude Code).

**Regras do setup:**
- Se `AGENTS.md` já existir → oferecer `improve` em vez de sobrescrever
- Se `CLAUDE.md` já for symlink → não recriar
- Se `CLAUDE.md` for arquivo regular → perguntar antes de substituir por symlink

**Após o setup, informe:**
- Arquivos criados
- Como preencher os context files conforme o projeto evoluir
- Como adicionar learnings: `bd remember "insight"` ou arquivo em `memory/` + linha no `MEMORY.md`

---

## Regras gerais

- Nunca modificar arquivos de context ao carregar — apenas ler
- Blocos auto-gerenciados por MCP servers são intocáveis
- Memory files são point-in-time — avisar quando > 7 dias sem atualização
- Se modo não reconhecido: listar comandos disponíveis e perguntar
