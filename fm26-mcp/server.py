"""
FM26 MCP Server — um co-treinador para Football Manager 26.

Lê exports de squad/shortlist do FM (HTML gerado por Squad > botão direito >
Print Screen > Web Page) e expõe ferramentas para:
  - análise de elenco (visão geral, busca, comparação)
  - fit tático (pontuar jogadores 0-100 por função tática)
  - mercado (carregar shortlist de scouting e cruzar com os buracos do elenco)
  - decisões de compra/venda (candidatos a venda, cota de não-UE da Ligue 1)

Filosofia de design (importante):
  - NÃO dependemos das estrelas de potencial (são relativas ao scout/elenco e
    portanto instáveis). Trabalhamos com ATRIBUTOS CRUS + idade + valor.
  - O "potencial" é inferido pelo assistente a partir de idade + atributos.
    As tools entregam os dados; o raciocínio acontece na conversa.

Como usar:
  1. No FM: Squad screen > view com o máximo de atributos > botão direito >
     Print Screen > Web Page (.html). Guarde o caminho.
  2. Registre este servidor no Claude Code (.mcp.json — ver README).
  3. Converse: "analise meu elenco", "quem serve como Deep-Lying Playmaker?",
     "carrega minha shortlist e me diz quais alvos valem a pena".
"""

import json
import re
from pathlib import Path
from typing import Optional
from html.parser import HTMLParser

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fm26-cotreinador")

# -----------------------------------------------------------------------------
# Estado: squad + shortlist carregados
# -----------------------------------------------------------------------------
STATE = {
    "squad": {"path": None, "players": [], "columns": []},
    "shortlist": {"path": None, "players": [], "columns": []},
}

# Nações tratadas como UE/equivalente na Ligue 1 (não gastam vaga de não-UE).
# Lista aproximada — confirme no seu save. Sul-americano com passaporte
# italiano/espanhol conta como UE (filtre por nacionalidade secundária).
EU_EQUIVALENT = {
    # UE/EEE
    "France", "Germany", "Spain", "Italy", "Portugal", "Netherlands", "Belgium",
    "Austria", "Poland", "Croatia", "Sweden", "Denmark", "Ireland", "Greece",
    "Czech Republic", "Romania", "Hungary", "Slovakia", "Slovenia", "Bulgaria",
    "Finland", "Norway", "Iceland", "Switzerland", "Luxembourg", "Cyprus",
    "Estonia", "Latvia", "Lithuania", "Malta",
    # ACP/tratados frequentemente tratados como equivalentes no FM (verifique in-game)
    "Morocco", "Algeria", "Tunisia", "Senegal", "Ivory Coast", "Cameroon",
    "Mali", "Nigeria", "Ghana", "DR Congo",
}

# Abreviações de coluna dos exports do FM -> nome canônico do atributo.
# Cobre as views padrão; nomes por extenso também são normalizados.
ATTR_ALIASES = {
    "acc": "acceleration", "aer": "aerial reach", "agg": "aggression",
    "agi": "agility", "ant": "anticipation", "bal": "balance", "bra": "bravery",
    "cmd": "command of area", "com": "communication", "cmp": "composure",
    "cnt": "concentration", "cor": "corners", "cro": "crossing",
    "dec": "decisions", "det": "determination", "dri": "dribbling",
    "ecc": "eccentricity", "fin": "finishing", "fir": "first touch",
    "fla": "flair", "fre": "free kick taking", "han": "handling",
    "hea": "heading", "jum": "jumping reach", "kic": "kicking",
    "ldr": "leadership", "lon": "long shots", "l th": "long throws",
    "mar": "marking", "nat fit": "natural fitness", "otb": "off the ball",
    "1v1": "one on ones", "pac": "pace", "pas": "passing",
    "pen": "penalty taking", "positioning": "positioning", "pun": "punching",
    "ref": "reflexes", "tro": "rushing out", "sta": "stamina",
    "str": "strength", "tck": "tackling", "tea": "teamwork",
    "tec": "technique", "thr": "throwing", "vis": "vision", "wor": "work rate",
}

# Funções táticas: pesos de atributo (nomes canônicos). Peso 3 = essencial,
# 2 = importante, 1 = útil. Score final normalizado 0-100.
ROLES = {
    "ball_playing_defender": {
        "passing": 3, "composure": 3, "tackling": 3, "marking": 3,
        "positioning": 3, "first touch": 2, "vision": 2, "decisions": 2,
        "jumping reach": 2, "strength": 2, "heading": 2, "technique": 1,
    },
    "deep_lying_playmaker": {
        "passing": 3, "vision": 3, "first touch": 3, "composure": 3,
        "technique": 2, "decisions": 2, "teamwork": 2, "anticipation": 1,
        "positioning": 1, "stamina": 1,
    },
    "inverted_wing_back": {
        "passing": 3, "decisions": 3, "work rate": 3, "technique": 2,
        "first touch": 2, "tackling": 2, "positioning": 2, "crossing": 1,
        "dribbling": 1, "acceleration": 1, "stamina": 1, "composure": 1,
    },
    "ball_winning_midfielder": {
        "tackling": 3, "aggression": 3, "work rate": 3, "stamina": 3,
        "anticipation": 2, "teamwork": 2, "bravery": 2, "marking": 1,
        "strength": 1, "concentration": 1,
    },
    "box_to_box": {
        "stamina": 3, "work rate": 3, "passing": 2, "tackling": 2,
        "off the ball": 2, "first touch": 2, "long shots": 1, "strength": 1,
        "dribbling": 1, "finishing": 1,
    },
    "advanced_playmaker": {
        "passing": 3, "vision": 3, "technique": 3, "first touch": 3,
        "flair": 2, "composure": 2, "decisions": 2, "dribbling": 2,
        "off the ball": 1, "agility": 1,
    },
    "winger": {
        "dribbling": 3, "crossing": 3, "pace": 3, "acceleration": 3,
        "technique": 2, "flair": 2, "agility": 2, "off the ball": 1,
        "first touch": 1, "work rate": 1,
    },
    "inside_forward": {
        "dribbling": 3, "finishing": 3, "pace": 2, "acceleration": 2,
        "off the ball": 2, "technique": 2, "long shots": 2, "first touch": 2,
        "composure": 1, "flair": 1,
    },
    "advanced_forward": {
        "finishing": 3, "off the ball": 3, "pace": 3, "acceleration": 2,
        "dribbling": 2, "first touch": 2, "composure": 2, "technique": 1,
        "anticipation": 1,
    },
    "pressing_forward": {
        "work rate": 3, "stamina": 3, "aggression": 2, "pace": 2,
        "bravery": 2, "teamwork": 2, "finishing": 2, "anticipation": 1,
        "strength": 1, "determination": 1,
    },
    "target_man": {
        "heading": 3, "jumping reach": 3, "strength": 3, "bravery": 2,
        "finishing": 2, "first touch": 1, "off the ball": 1, "teamwork": 1,
    },
    "sweeper_keeper": {
        "reflexes": 3, "one on ones": 3, "rushing out": 3, "kicking": 2,
        "passing": 2, "composure": 2, "decisions": 2, "handling": 2,
        "command of area": 1, "anticipation": 1,
    },
}


class SquadHTMLParser(HTMLParser):
    """Parser minimalista para a tabela de export HTML do FM."""
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.current_cell = ""
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def _to_int(val: str) -> Optional[int]:
    """Converte '16' ou '14-16' (range de scouting) em int. Range vira a média."""
    val = val.strip()
    if not val or val == "-":
        return None
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", val)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m = re.match(r"^(\d+)$", val)
    return int(m.group(1)) if m else None


def _parse_value(val: str) -> Optional[float]:
    """Converte valor de mercado ('€12.5M', '€850K', '€10M - €14M') em float
    (milhões). Range vira a média."""
    if not val:
        return None
    val = val.replace("€", "").replace("$", "").replace("£", "").strip()

    def one(s: str) -> Optional[float]:
        m = re.match(r"^([\d.,]+)\s*([MK]?)", s.strip(), re.IGNORECASE)
        if not m:
            return None
        num = float(m.group(1).replace(",", "."))
        unit = m.group(2).upper()
        return num / 1000 if unit == "K" else num

    if "-" in val:
        parts = [one(p) for p in val.split("-", 1)]
        parts = [p for p in parts if p is not None]
        return round(sum(parts) / len(parts), 2) if parts else None
    return one(val)


def _canonical_attr(col: str) -> str:
    """Normaliza um nome de coluna de atributo para o nome canônico."""
    c = col.lower().strip()
    return ATTR_ALIASES.get(c, c)


def _parse_file(path: str) -> dict:
    """Lê e parseia um export HTML do FM. Retorna dict com players/columns ou error."""
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"Arquivo não encontrado: {path}"}

    html = p.read_text(encoding="utf-8", errors="ignore")
    parser = SquadHTMLParser()
    parser.feed(html)

    if not parser.rows:
        return {"error": "Nenhuma tabela encontrada no HTML. É um export do FM?"}

    header = parser.rows[0]
    data_rows = parser.rows[1:]

    col_map = {}
    for i, col in enumerate(header):
        c = col.lower().strip()
        if c in ("name", "player", "nome"):
            col_map[i] = "name"
        elif c in ("age", "idade"):
            col_map[i] = "age"
        elif c in ("position", "pos", "posição", "posicao"):
            col_map[i] = "position"
        elif c in ("nat", "nation", "nationality", "nacionalidade"):
            col_map[i] = "nationality"
        elif c in ("value", "valor", "transfer value"):
            col_map[i] = "value"
        elif c in ("wage", "salary", "salário", "salario"):
            col_map[i] = "wage"
        elif c in ("club", "clube", "team"):
            col_map[i] = "club"
        else:
            col_map[i] = f"attr:{_canonical_attr(col)}"

    players = []
    for row in data_rows:
        if not any(cell.strip() for cell in row):
            continue
        player = {"attributes": {}}
        for i, cell in enumerate(row):
            if i not in col_map:
                continue
            key = col_map[i]
            if key == "age":
                player["age"] = _to_int(cell)
            elif key == "value":
                player["value_m"] = _parse_value(cell)
            elif key.startswith("attr:"):
                iv = _to_int(cell)
                if iv is not None:
                    player["attributes"][key[5:]] = iv
            else:
                player[key] = cell.strip()
        if player.get("name"):
            players.append(player)

    return {"players": players, "columns": header, "path": str(p)}


def _load_into(slot: str, path: str) -> str:
    result = _parse_file(path)
    if "error" in result:
        return json.dumps(result, ensure_ascii=False)
    STATE[slot]["path"] = result["path"]
    STATE[slot]["players"] = result["players"]
    STATE[slot]["columns"] = result["columns"]
    return json.dumps({
        "loaded": True,
        "slot": slot,
        "path": result["path"],
        "player_count": len(result["players"]),
        "columns_detected": result["columns"],
        "attributes_found": sorted(
            {a for pl in result["players"] for a in pl["attributes"]}
        ),
    }, ensure_ascii=False, indent=2)


def _players(slot: str = "squad") -> list:
    return STATE[slot]["players"]


def _role_score(player: dict, weights: dict) -> Optional[dict]:
    """Score 0-100 de um jogador para uma função. Retorna também a cobertura
    (fração dos pesos com atributo presente) — cobertura baixa = pouco confiável."""
    attrs = player["attributes"]
    total_w = sum(weights.values())
    have_w = 0
    acc = 0.0
    for attr, w in weights.items():
        v = attrs.get(attr)
        if v is not None:
            acc += w * v
            have_w += w
    if have_w == 0:
        return None
    return {
        "score": round(acc / (have_w * 20) * 100, 1),
        "coverage": round(have_w / total_w, 2),
    }


def _find_player(players: list, name: str) -> Optional[dict]:
    for p in players:
        if name.lower() in p.get("name", "").lower():
            return p
    return None


# -----------------------------------------------------------------------------
# TOOLS — carga de dados
# -----------------------------------------------------------------------------

@mcp.tool()
def load_squad(path: str) -> str:
    """Carrega o export HTML do SEU elenco (FM26). Rode isto primeiro.

    path = caminho para o .html exportado (Squad screen > Print Screen > Web Page).
    """
    return _load_into("squad", path)


@mcp.tool()
def load_shortlist(path: str) -> str:
    """Carrega um export HTML de shortlist/scouting (alvos de mercado).

    Mesmo formato do export de squad. Depois use shortlist_vs_squad ou
    score_for_role(source='shortlist') para avaliar os alvos.
    """
    return _load_into("shortlist", path)


# -----------------------------------------------------------------------------
# TOOLS — análise de elenco
# -----------------------------------------------------------------------------

@mcp.tool()
def squad_overview() -> str:
    """Visão geral do elenco: tamanho, idade média, distribuição por posição,
    veteranos (29+), jovens (21-) e valor total estimado."""
    players = _players()
    if not players:
        return "Nenhum elenco carregado. Rode load_squad primeiro."

    ages = [p["age"] for p in players if p.get("age")]
    positions = {}
    for p in players:
        pos = p.get("position", "?")
        positions[pos] = positions.get(pos, 0) + 1

    values = [p["value_m"] for p in players if p.get("value_m")]

    return json.dumps({
        "total": len(players),
        "idade_media": round(sum(ages) / len(ages), 1) if ages else None,
        "por_posicao": positions,
        "veteranos_29+": [p["name"] for p in players if p.get("age") and p["age"] >= 29],
        "jovens_21-": [p["name"] for p in players if p.get("age") and p["age"] <= 21],
        "valor_total_m": round(sum(values), 1) if values else None,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def search_players(
    max_age: Optional[int] = None,
    min_age: Optional[int] = None,
    position_contains: Optional[str] = None,
    nationality: Optional[str] = None,
    max_value_m: Optional[float] = None,
    min_attribute: Optional[str] = None,
    min_attribute_value: Optional[int] = None,
    non_eu_only: bool = False,
    sort_by_attribute: Optional[str] = None,
    source: str = "squad",
    limit: int = 20,
) -> str:
    """Busca jogadores por múltiplos filtros no elenco (source='squad') ou na
    shortlist (source='shortlist').

    Ex.: volantes jovens -> position_contains='DM', max_age=23
    Ex.: bons dribladores -> min_attribute='dribbling', min_attribute_value=14
    Ex.: só não-UE (cota da Ligue 1) -> non_eu_only=True
    Atributos aceitam nome completo ('passing') ou abreviação do FM ('Pas').
    sort_by_attribute ordena o resultado por um atributo (desc).
    """
    if source not in STATE:
        return "source deve ser 'squad' ou 'shortlist'."
    players = _players(source)
    if not players:
        return f"Nenhum dado em '{source}'. Rode load_{source} primeiro."

    min_attr = _canonical_attr(min_attribute) if min_attribute else None
    sort_attr = _canonical_attr(sort_by_attribute) if sort_by_attribute else None

    results = []
    for p in players:
        if max_age and (not p.get("age") or p["age"] > max_age):
            continue
        if min_age and (not p.get("age") or p["age"] < min_age):
            continue
        if position_contains and position_contains.lower() not in p.get("position", "").lower():
            continue
        if nationality and nationality.lower() not in p.get("nationality", "").lower():
            continue
        if max_value_m is not None and (p.get("value_m") is None or p["value_m"] > max_value_m):
            continue
        if non_eu_only and p.get("nationality") in EU_EQUIVALENT:
            continue
        if min_attr and min_attribute_value:
            av = p["attributes"].get(min_attr)
            if av is None or av < min_attribute_value:
                continue
        results.append(p)

    if sort_attr:
        results.sort(key=lambda x: x["attributes"].get(sort_attr, 0), reverse=True)

    trimmed = []
    for p in results[:limit]:
        trimmed.append({
            "name": p.get("name"),
            "age": p.get("age"),
            "position": p.get("position"),
            "nationality": p.get("nationality"),
            "club": p.get("club"),
            "value_m": p.get("value_m"),
            "key_attrs": dict(sorted(
                p["attributes"].items(), key=lambda kv: kv[1], reverse=True
            )[:8]),
        })
    return json.dumps({"count": len(results), "shown": trimmed}, ensure_ascii=False, indent=2)


@mcp.tool()
def compare_players(name_a: str, name_b: str) -> str:
    """Compara dois jogadores atributo por atributo. Procura nos dois slots
    (squad e shortlist), então serve pra comparar um alvo de compra com quem
    você já tem."""
    everyone = _players("squad") + _players("shortlist")
    if not everyone:
        return "Nenhum dado carregado. Rode load_squad (e/ou load_shortlist) primeiro."

    a = _find_player(everyone, name_a)
    b = _find_player(everyone, name_b)
    if not a or not b:
        missing = name_a if not a else name_b
        return f"Não achei '{missing}' no elenco nem na shortlist."

    all_attrs = sorted(set(a["attributes"]) | set(b["attributes"]))
    diff = []
    for attr in all_attrs:
        va = a["attributes"].get(attr, 0)
        vb = b["attributes"].get(attr, 0)
        if va != vb:
            diff.append({"attr": attr, a["name"]: va, b["name"]: vb, "delta": va - vb})
    diff.sort(key=lambda d: abs(d["delta"]), reverse=True)

    def head(p):
        return {"name": p["name"], "age": p.get("age"), "position": p.get("position"),
                "club": p.get("club"), "value_m": p.get("value_m")}

    return json.dumps({
        "a": head(a), "b": head(b), "maiores_diferencas": diff[:15],
    }, ensure_ascii=False, indent=2)


# -----------------------------------------------------------------------------
# TOOLS — fit tático
# -----------------------------------------------------------------------------

@mcp.tool()
def list_roles() -> str:
    """Lista as funções táticas disponíveis para score_for_role, com os pesos
    de atributo de cada uma (3 = essencial, 2 = importante, 1 = útil)."""
    return json.dumps(ROLES, ensure_ascii=False, indent=2)


@mcp.tool()
def score_for_role(
    role: str,
    position_contains: Optional[str] = None,
    source: str = "squad",
    limit: int = 15,
) -> str:
    """Pontua jogadores de 0-100 por quão bem servem a uma função tática.

    role = uma das funções de list_roles (ex.: 'deep_lying_playmaker').
    position_contains filtra por posição (ex.: 'DM'); source = 'squad' ou
    'shortlist'. 'coverage' indica a fração dos atributos da função presentes
    no export — abaixo de ~0.7, exporte uma view com mais colunas.
    """
    role_key = role.lower().strip().replace(" ", "_").replace("-", "_")
    if role_key not in ROLES:
        return json.dumps({
            "error": f"Função '{role}' desconhecida.",
            "disponiveis": sorted(ROLES.keys()),
        }, ensure_ascii=False)
    if source not in STATE:
        return "source deve ser 'squad' ou 'shortlist'."
    players = _players(source)
    if not players:
        return f"Nenhum dado em '{source}'. Rode load_{source} primeiro."

    weights = ROLES[role_key]
    scored = []
    for p in players:
        if position_contains and position_contains.lower() not in p.get("position", "").lower():
            continue
        s = _role_score(p, weights)
        if s is None:
            continue
        scored.append({
            "name": p.get("name"), "age": p.get("age"),
            "position": p.get("position"), "club": p.get("club"),
            "value_m": p.get("value_m"), **s,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    return json.dumps({
        "role": role_key, "source": source, "count": len(scored),
        "ranking": scored[:limit],
    }, ensure_ascii=False, indent=2)


# -----------------------------------------------------------------------------
# TOOLS — mercado (compra e venda)
# -----------------------------------------------------------------------------

@mcp.tool()
def shortlist_vs_squad(
    position_contains: str,
    role: Optional[str] = None,
    max_value_m: Optional[float] = None,
) -> str:
    """Cruza os alvos da shortlist com o seu elenco numa posição.

    Mostra, lado a lado, os alvos da shortlist e os seus jogadores atuais na
    posição — com score de função se 'role' for passado (ver list_roles).
    Use para responder 'este alvo é upgrade sobre quem eu tenho?'.
    """
    squad = _players("squad")
    targets = _players("shortlist")
    if not squad:
        return "Nenhum elenco carregado. Rode load_squad primeiro."
    if not targets:
        return "Nenhuma shortlist carregada. Rode load_shortlist primeiro."

    weights = None
    role_key = None
    if role:
        role_key = role.lower().strip().replace(" ", "_").replace("-", "_")
        if role_key not in ROLES:
            return json.dumps({
                "error": f"Função '{role}' desconhecida.",
                "disponiveis": sorted(ROLES.keys()),
            }, ensure_ascii=False)
        weights = ROLES[role_key]

    def rows(players, is_target):
        out = []
        for p in players:
            if position_contains.lower() not in p.get("position", "").lower():
                continue
            if is_target and max_value_m is not None and (
                p.get("value_m") is None or p["value_m"] > max_value_m
            ):
                continue
            row = {
                "name": p.get("name"), "age": p.get("age"),
                "position": p.get("position"), "club": p.get("club"),
                "nationality": p.get("nationality"), "value_m": p.get("value_m"),
                "non_eu": bool(p.get("nationality")) and p["nationality"] not in EU_EQUIVALENT,
            }
            if weights:
                s = _role_score(p, weights)
                if s:
                    row.update(s)
            out.append(row)
        out.sort(key=lambda r: r.get("score", 0), reverse=True)
        return out

    return json.dumps({
        "posicao": position_contains,
        "role": role_key,
        "alvos_shortlist": rows(targets, True),
        "elenco_atual": rows(squad, False),
        "nota": "non_eu=True gasta vaga da cota de 4 da Ligue 1 (ver non_eu_check).",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def non_eu_check() -> str:
    """Conta os jogadores não-UE do elenco contra a cota de 4 da Ligue 1 e
    mostra quantas vagas livres você tem (essencial antes de comprar não-UE)."""
    players = _players()
    if not players:
        return "Nenhum elenco carregado. Rode load_squad primeiro."

    non_eu = [
        {"name": p["name"], "nationality": p.get("nationality"), "age": p.get("age")}
        for p in players
        if p.get("nationality") and p["nationality"] not in EU_EQUIVALENT
    ]
    return json.dumps({
        "cota_maxima": 4,
        "ocupadas": len(non_eu),
        "vagas_livres": max(0, 4 - len(non_eu)),
        "jogadores_nao_ue": non_eu,
        "nota": "Lista EU_EQUIVALENT é aproximada — confirme no jogo. "
                "Sul-americano com passaporte italiano/espanhol NÃO conta como não-UE.",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def sell_candidates(max_keep_age: int = 30) -> str:
    """Sugere candidatos a venda: veteranos (idade >= max_keep_age) com valor
    de mercado ainda alto, jogadores no pico de valorização (24-28 com valor
    alto), e posições lotadas (4+ jogadores). Retorna dados crus para o
    assistente raciocinar sobre quem vender, quando e por quanto."""
    players = _players()
    if not players:
        return "Nenhum elenco carregado. Rode load_squad primeiro."

    veterans = sorted(
        [p for p in players if p.get("age") and p["age"] >= max_keep_age and p.get("value_m")],
        key=lambda x: x["value_m"], reverse=True,
    )
    peak_value = sorted(
        [p for p in players
         if p.get("age") and 24 <= p["age"] <= 28 and p.get("value_m")],
        key=lambda x: x["value_m"], reverse=True,
    )
    by_pos = {}
    for p in players:
        by_pos.setdefault(p.get("position", "?"), []).append(p["name"])
    redundant = {pos: names for pos, names in by_pos.items() if len(names) >= 4}

    def brief(p):
        return {"name": p["name"], "age": p["age"], "position": p.get("position"),
                "value_m": p["value_m"]}

    return json.dumps({
        "veteranos_vendaveis": [brief(p) for p in veterans[:10]],
        "pico_de_valor_24_28": [brief(p) for p in peak_value[:10]],
        "posicoes_lotadas": redundant,
        "nota": "Regra de ouro: venda 1-2 anos ANTES do declínio (28-29 para "
                "a maioria; antes para jogadores de velocidade). Peça 1.5-2x "
                "o valor de mercado em negociação.",
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
