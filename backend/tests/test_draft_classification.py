import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.ai import get_ai_provider
from app.domain.draft_classification import category_fallback, priority_fallback
from app.models import Category
from tests.test_ollama import install_http, response
from app.services.ai.ollama import OllamaAIProvider


@pytest.mark.parametrize('text,category', [
    ("L'ascensore è bloccato al terzo piano e non riparte", 'Ascensore'),
    ('Gli elevatori sono guasti', 'Ascensore'),
    ("Perdita d'acqua", 'Idraulico'), ('Il lavandino gocciola', 'Idraulico'),
    ('I condizionatori sono guasti', 'Climatizzazione'),
    ('Aria condizionata guasta', 'Climatizzazione'),
    ('La serratura è rotta', 'Serramenti'), ('Gli infissi sono rotti', 'Serramenti'),
    ('Caldaia guasta', 'Riscaldamento'), ('Presa elettrica rotta', 'Elettrico'),
    ('Quadro elettrico guasto', 'Elettrico'), ('Wi-Fi guasto', 'Rete'),
    ('Vetrata rotta', 'Vetri'), ('Crepe nel muro', 'Edile'),
    ('Rilevatore di fumo guasto', 'Antincendio'), ('Telecamere guaste', 'Sicurezza'),
    ('Scrivania rotta', 'Arredi'), ('Ascensore e rubinetto guasti', None),
    ("Non c'è perdita d'acqua", None), ('Nessun allagamento', None),
    ('Esempio: ascensore bloccato', None), ('"Ascensore bloccato"', None),
    ("'ascensore bloccato'", None), ('Informazioni generiche', None),
])
def test_category_signals(text, category):
    assert category_fallback(text) == category


@pytest.mark.parametrize('text,priority', [
    ("L'ascensore è bloccato al terzo piano e non riparte", 'ALTA'),
    ("Una persona è bloccata dentro l'ascensore", 'URGENTE'),
    ('Ascensore bloccato', 'ALTA'), ('Ascensore non riparte', 'ALTA'),
    ("L'ascensore funziona ma vorrei informazioni", None),
    ('Ascensore non bloccato', None), ('Urgente urgente!', None),
    ('Non ci sono persone intrappolate; ascensore bloccato', 'ALTA'),
    ('Incendio nel locale', 'URGENTE'), ('Non c è incendio', None),
    ('Rilevatore fumo guasto', 'MEDIA'),
    ('Fumo visibile nel locale', 'URGENTE'), ('C è fumo', 'URGENTE'),
    ('Non c è fumo', None),
    ('Grave rischio elettrico', 'URGENTE'),
    ('Forte perdita con rischio di danni immediati', 'URGENTE'),
    ('Interruzione totale della rete', 'ALTA'),
    ('Riscaldamento completamente assente', 'ALTA'),
    ('Rubinetto guasto', 'MEDIA'), ('Piccolo inconveniente', 'BASSA'),
    ('Manutenzione programmata', 'PROGRAMMABILE'),
    ('Manutenzione programmata ma incendio', 'URGENTE'),
    ('Non c è perdita d acqua', None), ('"Incendio nel locale"', None),
])
def test_priority_signals(text, priority):
    assert priority_fallback(text) == priority


MARCO_REPORT = (
    "Buongiorno mi chiamo Marco, vorrei segnalare riscaldamento non "
    "funzionante in Via Carducci 16 a Preganziol (TV), potete contattarmi al "
    "cel. 3286677356 oppure via mail a marco@test.com"
)


@pytest.mark.parametrize('text,priority', [
    ('riscaldamento non funzionante', 'MEDIA'),
    (MARCO_REPORT, 'MEDIA'),
    (MARCO_REPORT.replace('non funzionante', 'non\nfunzionante'), 'MEDIA'),
    ("tutto l'edificio è senza riscaldamento", 'ALTA'),
    ('riscaldamento completamente assente', 'ALTA'),
    ('internet completamente assente', 'ALTA'),
    ('rete completamente assente', 'ALTA'),
    ('blackout totale', 'ALTA'),
    ('blackout', None),
    ('riscaldamento fuori servizio', 'MEDIA'),
    ('ascensore bloccato e non riparte', 'ALTA'),
    ("persona bloccata nell'ascensore", 'URGENTE'),
    ("Ci sono persone intrappolate nell'ascensore", 'URGENTE'),
    ('Ci sono persone intrappolate', 'URGENTE'),
    ('presa fa scintille e ci sono cavi scoperti', 'URGENTE'),
    ('odore forte di gas', 'URGENTE'),
    ('fuga di gas', 'URGENTE'),
    ('grave allagamento', 'URGENTE'),
    ('acqua che sta causando danni immediati', 'URGENTE'),
    ('guasto grave che impedisce il normale uso', 'ALTA'),
    ('guasto che impedisce il normale uso', 'ALTA'),
    ('condizionatore non raffredda', 'MEDIA'),
    ('condizionatore non funziona', 'MEDIA'),
    ('rubinetto perde', 'MEDIA'),
    ('porta non si chiude correttamente', 'MEDIA'),
    ('piccolo difetto, apparecchio ancora utilizzabile', 'BASSA'),
    ('piccolo difetto con apparecchio ancora utilizzabile', 'BASSA'),
    ('componente allentato ma ancora utilizzabile', 'BASSA'),
    ('componente allentato e ancora utilizzabile', 'BASSA'),
    ('piccolo graffio', 'BASSA'),
    ('lieve rumore', 'BASSA'),
    ('lieve deterioramento ancora utilizzabile', 'BASSA'),
    ('lieve deterioramento', None),
    ('lieve malfunzionamento ma rubinetto perde', 'MEDIA'),
    ('lieve malfunzionamento ma apparecchio non utilizzabile', 'MEDIA'),
    ('manutenzione programmata e condizionatore non raffredda', 'MEDIA'),
    ('piccolo graffio e manutenzione programmata', 'BASSA'),
    ('controllo periodico', 'PROGRAMMABILE'),
    ('sostituzione preventiva', 'PROGRAMMABILE'),
    ('verniciatura', 'PROGRAMMABILE'),
    ('regolazione non urgente', 'PROGRAMMABILE'),
    ("non c'è pericolo", None),
    ("non c'è pericolo e condizionatore non raffredda", 'MEDIA'),
    ("non c'è pericolo, riscaldamento non funzionante", 'MEDIA'),
    ("non c'è perdita", None),
    ('nessun rischio elettrico', None),
    ('non ci sono scintille né cavi scoperti', None),
    ('non ci sono scintille e cavi scoperti', None),
    ("non c'è pericolo e ci sono cavi scoperti", 'URGENTE'),
    ('non ci sono persone bloccate', None),
    ('non è vero che riscaldamento non funziona', None),
    ("tutto l'edificio non è senza riscaldamento", None),
    ('ascensore non bloccato e funziona', None),
    ('condizionatore non funziona male', None),
    ('urgente', None),
    ('Vorrei informazioni', None),
    ('Riscaldamento', None),
    ('Sono Fumo Incendio, telefono 3331234567', None),
    ('Mi chiamo Incendio', None),
    ('Contattatemi a incendio.scintille@test.com', None),
    ('Il guasto è in via del Fumo 20', 'MEDIA'),
    ('Indirizzo: via del Fumo 20', None),
    ('Indirizzo: via Roma 20, Fumo', None),
    ('Indirizzo: via del Fumo 20: condizionatore non funziona', 'MEDIA'),
    ('Località: Incendio', None),
])
def test_conservative_priority_hierarchy(text, priority):
    assert priority_fallback(text) == priority


@pytest.mark.parametrize('priority', ['PROGRAMMABILE', 'BASSA', 'MEDIA', 'ALTA', 'URGENTE'])
def test_valid_ollama_priority_skips_priority_classifier(api, monkeypatch, priority):
    client, _ = api
    install_http(monkeypatch, lambda request: response({'priority': priority}))
    client.app.dependency_overrides[get_ai_provider] = lambda: OllamaAIProvider(
        'http://localhost:11434', 'test-model', 60,
    )

    def unexpected_fallback(text):
        pytest.fail('A valid Ollama priority must skip the deterministic classifier')

    monkeypatch.setattr('app.services.work_order_drafts.priority_fallback', unexpected_fallback)
    result = client.post('/api/ai/work-order-draft', json={'text': 'Incendio nel locale'})
    assert result.status_code == 200
    assert result.json()['priority'] == priority
    assert not any('Priorità proposta tramite regole' in w for w in result.json()['warnings'])


@pytest.mark.parametrize('proposal', [{}, {'priority': None}])
def test_missing_ollama_priority_uses_original_report(api, monkeypatch, proposal):
    client, _ = api
    install_http(monkeypatch, lambda request: response({
        **proposal, 'description': 'Manutenzione programmata.',
    }))
    client.app.dependency_overrides[get_ai_provider] = lambda: OllamaAIProvider(
        'http://localhost:11434', 'test-model', 60,
    )
    result = client.post('/api/ai/work-order-draft', json={'text': MARCO_REPORT})
    assert result.status_code == 200
    assert result.json()['priority'] == 'MEDIA'
    assert result.json()['description'] == 'Manutenzione programmata.'
    assert any('Priorità proposta tramite regole' in w for w in result.json()['warnings'])


@pytest.mark.parametrize('proposal', [{}, {'category_name': 'Non configurata'},
                                      {'category_name': 'Idraulico'}, {'priority': 'BASSA'},
                                      {'category_name': 'Idraulico', 'priority': 'BASSA'}])
def test_ollama_fallback_preserves_valid_proposals_and_never_writes(api, monkeypatch, proposal):
    client, engine = api
    with Session(engine) as db:
        db.add(Category(id=89, name='ASCENSORE'))
        db.commit()
    install_http(monkeypatch, lambda request: response({**proposal, 'description': 'Sintesi tecnica.'}))
    client.app.dependency_overrides[get_ai_provider] = lambda: OllamaAIProvider(
        'http://localhost:11434', 'test-model', 60
    )
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(engine, 'before_cursor_execute', observe)
    try:
        result = client.post('/api/ai/work-order-draft', json={
            'text': "L'ascensore è bloccato al terzo piano e non riparte"
        })
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert result.status_code == 200
    draft = result.json()
    valid = proposal.get('category_name') == 'Idraulico'
    assert draft['category_id'] == (2 if valid else 89)
    assert draft['category_name'] == ('Idraulico' if valid else 'ASCENSORE')
    assert draft['priority'] == proposal.get('priority', 'ALTA')
    assert draft['description'] == 'Sintesi tecnica.'
    assert set(statements) <= {'SELECT'}
    assert client.get('/api/work-orders').json() == []
    assert any('deterministiche' in w for w in draft['warnings']) == (not valid or 'priority' not in proposal)


@pytest.mark.parametrize('names,text', [
    ([], 'Ascensore bloccato'),
    (['Ascensore', ' ASCENSORE '], 'Ascensore bloccato'),
    (['Ascensore'], 'Ascensore e lavandino guasti'),
])
def test_fallback_requires_unique_configured_category(api, monkeypatch, names, text):
    client, engine = api
    with Session(engine) as db:
        db.add_all(Category(id=80 + i, name=name) for i, name in enumerate(names))
        db.commit()
    install_http(monkeypatch, lambda request: response({}))
    client.app.dependency_overrides[get_ai_provider] = lambda: OllamaAIProvider(
        'http://localhost:11434', 'test-model', 60
    )
    draft = client.post('/api/ai/work-order-draft', json={'text': text}).json()
    assert draft['category_id'] is None
    assert draft['category_name'] is None
    assert any('manual' in w for w in draft['warnings'])
