<div align="center">
  <h1>📊 ValuaçãoBR 2.0</h1>
  <p><b>Análise de Ativos, Preço Justo e Controle Financeiro Automatizado</b></p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Streamlit-1.35+-FF4B4B.svg" alt="Streamlit">
    <img src="https://img.shields.io/badge/FastAPI-Backend-009688.svg" alt="FastAPI">
    <img src="https://img.shields.io/badge/Database-SQLite-003B57.svg" alt="SQLite">
    <img src="https://img.shields.io/badge/Open_Finance-Pluggy-blueviolet.svg" alt="Pluggy">
  </p>
</div>

O **ValuaçãoBR** nasceu como um sistema de cálculo de preço justo para investidores em Ações e Fundos Imobiliários na Bolsa de Valores Brasileira (B3). Na sua versão **2.0**, ele evoluiu para um ecossistema financeiro completo, incorporando integração *Open Finance* para o monitoramento contínuo das suas despesas e receitas bancárias.

Com uma interface moderna no padrão *Premium Dark*, foco total em dados armazenados localmente e um backend independente, o sistema garante agilidade extrema e respeito absoluto à privacidade dos seus dados financeiros.

---

## 🎯 Principais Funcionalidades

### 📈 1. Análise de Ativos (Valuation)
- **6 Modelos Matemáticos:** Cálculo simultâneo usando fórmulas de Benjamin Graham, Décio Bazin, Modelo de Gordon (DDM), Fluxo de Caixa Descontado (FCD), Múltiplos Setoriais (EV/EBITDA) e o método projetivo de Warren Buffett.
- **Score Qualitativo (Risco):** Avaliação profunda do balanço da empresa, penalizando empresas com alta dívida (Dívida/EBITDA > 3) e bonificando caixas líquidos e consistência de proventos.
- **Dashboard FIIs:** Interface especializada para extração e agrupamento por Dividend Yield (DY), P/VP e Setor.

### 💳 2. Controle de Gastos Automatizado (Open Finance)
- **Integração Pluggy.ai:** Sincronização segura de histórico bancário e cartões de crédito utilizando a API da [Pluggy](https://pluggy.ai/).
- **Filtro Anti-Distorção:** Motor inteligente para ignorar transações entre contas do mesmo titular e pagamentos de fatura, evitando que o patrimônio e os gastos sejam contabilizados em duplicidade.
- **Gráficos com Drill-down:** Clicar num mês no gráfico de histórico automaticamente expande os gastos específicos daquele período na grade de detalhamento.

### 🔒 3. Privacidade e Arquitetura Offline-First
- Todos os relatórios gerados e transações raspadas da nuvem ficam armazenadas num **banco de dados SQLite local**. Não dependemos de nuvem de terceiros para guardar seu balanço.
- Comunicação interna backend/frontend (FastAPI ⇄ Streamlit) processa cálculos delicados e gerencia chaves no lado servidor local.

---

## 🚀 Como Executar o Projeto Localmente

### Pré-requisitos
- **Python 3.11** ou superior instalado.
- Chaves de acesso ao portal [Pluggy.ai](https://dashboard.pluggy.ai) (Client ID e Secret).

### Instalação

1. **Clone o repositório principal e seu submódulo de API:**
   ```bash
   git clone --recursive https://github.com/RKetson/Analise_Tickers.git
   cd Analise_Tickers
   ```

2. **Execute o Script de Instalação Automática:**
   Para criar o ambiente virtual, baixar todas as bibliotecas necessárias para o Frontend/Backend e gerar o arquivo de configuração, basta dar um duplo clique em:
   ```cmd
   install_app.bat
   ```
   *(Ou execute no terminal se preferir).*

3. **Configuração de Segredos:**
   O script criará o arquivo `.env` dentro da pasta `API_pluggy`. Abra este arquivo num editor de texto e preencha com suas credenciais do portal Pluggy.ai.
   Em seguida, gere uma chave de segurança para o seu banco de dados local com este comando (você precisa estar com o ambiente ativado):
   ```bash
   .venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Cole essa chave no campo `DB_ENCRYPTION_KEY` dentro do `.env`.

### ⚡ Inicialização Rápida

Para iniciar a orquestração do Backend e do Frontend, o projeto conta com scripts utilitários prontos.

Basta dar dois cliques (ou executar via terminal):
```cmd
start_app.bat
```
*(Ele abrirá os serviços silenciosamente em segundo plano).*

- O sistema principal estará disponível em: `http://localhost:8501`
- A API documentada estará disponível em: `http://localhost:8000/docs`

Se desejar visualizar as mensagens de log no terminal para depuração:
```cmd
start_app.bat debug
```

Para encerrar a aplicação com segurança (matar os processos em background):
```cmd
stop_app.bat
```

---

## 🛠 Arquitetura do Sistema

O ValuaçãoBR divide as responsabilidades em pequenos microsserviços monorrepositórios:
- `app.py`: Ponto de entrada do Frontend, roteador Streamlit, gerenciador de estado.
- `src/models.py`: Motor de cálculos e travas matemáticas isolado da interface.
- `src/data_loader.py`: ORM via SQLAlchemy conectando-se ao `data/analise_tickers.sqlite`.
- `API_pluggy/`: Submódulo contendo um servidor FastAPI focado exclusivamente nas transações e webhooks.

## 🤝 Contribuindo
Sinta-se à vontade para abrir Issues e enviar Pull Requests! Novas integrações financeiras e refinamentos de IA para análise patrimonial são sempre bem-vindos.

---
*Este projeto foi arquitetado por renna (e refinado por Inteligência Artificial avançada) para uso contínuo e acompanhamento de rentabilidade do mercado brasileiro.*
