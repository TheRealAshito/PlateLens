# PlateLens

**Diário alimentar self-hosted em PT-BR com estimativa de calorias e macronutrientes por foto do prato, Tabela TACO e calculadora TMB/TDEE.**

Nenhuma chave de API vem embutida no projeto: ao iniciar o aplicativo pela primeira vez sem `.env`, a interface solicita sua chave do **Google AI Studio (Gemini)** — ou permite usar apenas a busca manual na **Tabela TACO** offline.

---

## Recursos

- **Análise de prato por foto:** envie uma foto pela câmera do celular ou galeria; a IA identifica os alimentos, estima as porções em gramas e alerta sobre possíveis calorias ocultas (azeite, molhos, preparo).
- **Motor nutricional determinístico (Tabela TACO):** cruza os alimentos identificados com uma base local em SQLite (com busca sem acentos) para calcular **kcal, proteínas, carboidratos, gorduras e fibras**.
- **Revisão rápida antes de salvar:** ajuste gramas (`-25g / +25g`), aplique medidas caseiras ou adicione itens extras com recálculo instantâneo sem gastar nova chamada de IA.
- **Estratégia inteligente de cota gratuita (Gemini):** usa **`gemini-3.6-flash`** como padrão e faz fallback automático para **`gemini-3.5-flash-lite`** caso ocorra erro `429` de limite diário, além de permitir alternar o modo diretamente na tela.
- **Suporte opcional a Ollama na LAN:** configure `OLLAMA_BASE_URL` caso possua outra máquina com GPU na sua rede local.
- **Calculadora TMB / TDEE (Mifflin-St Jeor):** calcule sua meta calórica e divisão de macronutrientes e acompanhe a evolução em gráficos de 7 e 30 dias.
- **100% self-hosted:** banco SQLite e fotos armazenados localmente em `./data`.

---

## Subir com Docker Compose (Homelab)

```bash
git clone https://github.com/<seu-usuario>/PlateLens.git
cd PlateLens
docker compose up -d --build
```

Acesse **`http://<ip-do-homelab>:8502`** no computador ou celular.

> **Configuração inicial:** Ao abrir a WebUI pela primeira vez, um assistente pedirá sua chave do [Google AI Studio](https://aistudio.google.com/) (Free Tier funciona sem depósito pré-pago). Se preferir, você também pode criar um `.env` baseado no `.env.example` antes de subir o container.

---

## Desenvolvimento Local

### Backend (FastAPI)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8502
```

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

### Testes Automatizados

```bash
pytest -v
```

---

## Aviso Importante

Estimativas calóricas a partir de fotografias 2D possuem margem de erro aproximada (especialmente por densidade dos alimentos e óleos/molhos ocultos). O PlateLens é uma ferramenta de apoio organizacional e educativa e não substitui acompanhamento nutricional ou médico.
