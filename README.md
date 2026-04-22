# prime-context — Claude Code Skill

Skill para gerenciar contexto de projetos de forma eficiente em sessões do Claude Code.

## Filosofia

`AGENTS.md` deve ser **fino**. Ele é carregado em toda sessão — cada linha desperdiça tokens.
O conteúdo detalhado vai em `.claude/context/<área>.md` e é lido **só quando a tarefa exige**.

## Comandos

| Comando | O que faz |
|---------|-----------|
| `/prime-context` | Carrega contexto geral do projeto atual |
| `/prime-context <área>` | Carrega contexto de uma área específica (ex: `filament`, `api`, `prod`) |
| `/prime-context improve` | Refatora um `AGENTS.md` gordo → thin + `.claude/context/` files |
| `/prime-context setup` | Configura a estrutura de contexto em um novo projeto do zero |

## Como instalar

```bash
# Clonar na pasta de skills do Claude Code
git clone https://github.com/rodrigopg/claude-skill-prime-context ~/.claude/skills/prime-context
```

## Estrutura gerada pelo `improve` / `setup`

```
projeto/
├── AGENTS.md               # Fino: visão geral + tabela de roteamento + regras + checklist
├── CLAUDE.md               # Symlink → AGENTS.md
└── .claude/
    └── context/
        ├── filament.md     # Carregado só quando trabalhar com Filament
        ├── api.md          # Carregado só quando trabalhar na API
        ├── db.md           # Carregado só quando precisar do schema
        ├── prod.md         # Carregado só para deploy/infra
        └── <área>.md       # Uma por domínio de trabalho
```
