from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import time
import math
import sys
import random

# ======= Definições básicas =======
SIZE_MAP = {"P": 1, "M": 2, "G": 3}
SIZE_LETTER = {1: "P", 2: "M", 3: "G"}

PLAYERS = ("H", "I")  # H = Humano, I = IA
HUMAN, AI = 0, 1

Coord = Tuple[int, int]  # (row, col) com 0..2
Piece = Tuple[int, int]  # (player, size_int)

LINES: List[List[Coord]] = [
    # linhas
    [(0, 0), (0, 1), (0, 2)],
    [(1, 0), (1, 1), (1, 2)],
    [(2, 0), (2, 1), (2, 2)],
    # colunas
    [(0, 0), (1, 0), (2, 0)],
    [(0, 1), (1, 1), (2, 1)],
    [(0, 2), (1, 2), (2, 2)],
    # diagonais
    [(0, 0), (1, 1), (2, 2)],
    [(0, 2), (1, 1), (2, 0)],
]

def cell_name_to_coord(s: str) -> Optional[Coord]:
    s = s.strip().upper()
    if len(s) != 2:
        return None
    rmap = {"A": 0, "B": 1, "C": 2}
    cmap = {"1": 0, "2": 1, "3": 2}
    if s[0] in rmap and s[1] in cmap:
        return rmap[s[0]], cmap[s[1]]
    return None

def coord_to_cell_name(rc: Coord) -> str:
    r, c = rc
    rmap = "ABC"
    cmap = "123"
    return f"{rmap[r]}{cmap[c]}"

# ======= Estado do jogo =======
@dataclass
class State:
    # board[r][c] é uma pilha (lista) de Piece; topo é o fim da lista
    board: List[List[List[Piece]]] = field(default_factory=lambda: [[[] for _ in range(3)] for _ in range(3)])
    # reservas[player][size] = qtd (size em {1,2,3})
    reserves: List[Dict[int, int]] = field(default_factory=lambda: [{1: 2, 2: 2, 3: 2} for _ in range(2)])
    to_move: int = HUMAN
    history_tops: List[Tuple[Optional[Piece], ...]] = field(default_factory=list)  # para repetição simples

    def copy(self) -> "State":
        new = State()
        new.board = [[cell.copy() for cell in row] for row in self.board]
        new.reserves = [{k: v for k, v in res.items()} for res in self.reserves]
        new.to_move = self.to_move
        new.history_tops = self.history_tops.copy()
        return new

    def top(self, rc: Coord) -> Optional[Piece]:
        r, c = rc
        return self.board[r][c][-1] if self.board[r][c] else None

    def push(self, rc: Coord, piece: Piece) -> None:
        r, c = rc
        self.board[r][c].append(piece)

    def pop(self, rc: Coord) -> Piece:
        r, c = rc
        return self.board[r][c].pop()

    def tops_signature(self) -> Tuple[Optional[Piece], ...]:
        # só os topos; suficiente para detectar loops mais comuns
        sig = []
        for r in range(3):
            for c in range(3):
                sig.append(self.top((r, c)))
        return tuple(sig)

# ======= Regras e utilitários =======
def legal_places_from_reserve(st: State, player: int) -> List[Tuple[str, int, Coord]]:
    moves: List[Tuple[str, int, Coord]] = []
    for size, qty in st.reserves[player].items():
        if qty <= 0:
            continue
        for r in range(3):
            for c in range(3):
                t = st.top((r, c))
                if t is None or t[1] < size:
                    moves.append(("place", size, (r, c)))
    return moves

def legal_moves_on_board(st: State, player: int) -> List[Tuple[str, Coord, Coord]]:
    moves: List[Tuple[str, Coord, Coord]] = []
    for r in range(3):
        for c in range(3):
            t = st.top((r, c))
            if t is None or t[0] != player:
                continue
            size = t[1]
            for rr in range(3):
                for cc in range(3):
                    if (rr, cc) == (r, c):
                        continue
                    t2 = st.top((rr, cc))
                    if t2 is None or t2[1] < size:
                        moves.append(("move", (r, c), (rr, cc)))
    return moves

def legal_moves(st: State, player: int) -> List[Tuple]:
    return legal_places_from_reserve(st, player) + legal_moves_on_board(st, player)

def apply_move(st: State, mv: Tuple) -> State:
    ns = st.copy()
    if mv[0] == "place":
        _, size, dst = mv
        assert ns.reserves[ns.to_move][size] > 0
        ns.reserves[ns.to_move][size] -= 1
        ns.push(dst, (ns.to_move, size))
    else:  # "move"
        _, src, dst = mv
        piece = ns.top(src)
        assert piece and piece[0] == ns.to_move
        ns.pop(src)
        tdst = ns.top(dst)
        assert (tdst is None) or (tdst[1] < piece[1])
        ns.push(dst, piece)
    ns.to_move = 1 - ns.to_move
    ns.history_tops.append(ns.tops_signature())
    return ns

def winner(st: State) -> Optional[int]:
    # Vitória se 3 topos visíveis do mesmo jogador alinhados
    for line in LINES:
        tops = [st.top(rc) for rc in line]
        if None in tops:
            continue
        owners = [p[0] for p in tops if p is not None]
        if len(owners) == 3 and owners.count(owners[0]) == 3:
            return owners[0]
    return None

def terminal(st: State) -> bool:
    if winner(st) is not None:
        return True
    # repetição simples: mesma assinatura de topos 3 vezes
    if st.history_tops.count(st.tops_signature()) >= 2:
        return True
    # sem lances legais (raro)
    if not legal_moves(st, st.to_move):
        return True
    return False

# ======= Heurística =======
# Pesos ajustáveis
W1, W2, Wc, Wk, WG, WM, WP, Wm, Wcover, Wself = 300, 40, 60, 25, 30, 18, 10, 4, 25, 5

def largest_available_size(st: State, player: int) -> int:
    # maior tamanho que o player pode colocar/mover agora
    max_from_reserve = max((s for s, q in st.reserves[player].items() if q > 0), default=0)
    max_on_board = 0
    for r in range(3):
        for c in range(3):
            t = st.top((r, c))
            if t is not None and t[0] == player:
                max_on_board = max(max_on_board, t[1])
    return max(max_from_reserve, max_on_board)

def cell_accessible_by_player(st: State, rc: Coord, player: int) -> bool:
    t = st.top(rc)
    if t is None:
        return True
    return t[1] < largest_available_size(st, player)

def heuristic(st: State, player: int) -> int:
    opp = 1 - player
    w = winner(st)
    if w == player:
        return 10**9
    if w == opp:
        return -10**9

    score = 0
    # Centro e cantos
    center = (1, 1)
    t = st.top(center)
    if t:
        score += (Wc if t[0] == player else -Wc)
    for rc in [(0,0),(0,2),(2,0),(2,2)]:
        t = st.top(rc)
        if t:
            score += (Wk if t[0] == player else -Wk)

    # Linhas (ameaças)
    for line in LINES:
        tops = [st.top(rc) for rc in line]
        owners = [p[0] if p else None for p in tops]
        # Minha linha
        my_count = owners.count(player)
        opp_count = owners.count(opp)
        empty_idxs = [i for i, x in enumerate(owners) if x is None]
        if opp_count == 0:
            if my_count == 2:
                # terceira casa precisa ser "acessível"
                rc = line[empty_idxs[0]]
                if cell_accessible_by_player(st, rc, player):
                    score += W1
            elif my_count == 1:
                score += W2
        # Linha do oponente
        if my_count == 0:
            if opp_count == 2:
                rc = line[empty_idxs[0]]
                if cell_accessible_by_player(st, rc, opp):
                    score -= W1
            elif opp_count == 1:
                score -= W2

    # Recursos nas reservas
    gr = st.reserves[player]
    orr = st.reserves[opp]
    score += (gr.get(3,0)-orr.get(3,0))*WG + (gr.get(2,0)-orr.get(2,0))*WM + (gr.get(1,0)-orr.get(1,0))*WP

    # Mobilidade (diferença do nº de lances)
    score += Wm * (len(legal_moves(st, player)) - len(legal_moves(st, opp)))

    return score

# ======= Ordenação de lances =======
def is_winning_move(st: State, mv: Tuple, player: int) -> bool:
    return winner(apply_move(st, mv)) == player

def blocks_opponent_win(st: State, mv: Tuple, player: int) -> bool:
    # após o meu mv, o oponente ainda tem algum lance ganhador imediato?
    ns = apply_move(st, mv)
    opp = 1 - player
    for omv in legal_moves(ns, opp):
        if is_winning_move(ns, omv, opp):
            return False
    return True

def move_sort_key(st: State, mv: Tuple, player: int) -> Tuple[int, int, int]:
    # Ranking: ganhar agora > bloquear > centro > canto > outros
    score = 0
    if is_winning_move(st, mv, player):
        score += 10000
    elif blocks_opponent_win(st, mv, player):
        score += 2000
    # preferir centro/cantos ao colocar/mover
    dest: Optional[Coord] = None
    if mv[0] == "place":
        _, _, dest = mv
    else:
        _, _, dest = mv
    if dest == (1, 1):
        score += 50
    elif dest in {(0,0),(0,2),(2,0),(2,2)}:
        score += 20
    # lances que cobrem peça adversária valem um extra
    if dest is not None:
        t = st.top(dest)
        if t is not None and t[0] != player:
            score += 15
    # preferir peças maiores
    if mv[0] == "place":
        score += mv[1]
    else:
        src = mv[1]
        t = st.top(src)
        if t:
            score += t[1]
    return (-score, 0, 0)  # negativo para ordenar crescente → maior prioridade primeiro

# ======= Minimax α-β com tempo =======
class Timeout(Exception):
    pass

def minimax_iterative_deepening(root: State, for_player: int, time_limit: float = 30.0, max_depth: int = 12) -> Tuple[int, Optional[Tuple]]:
    deadline = time.time() + time_limit
    best_move = None
    best_val = -math.inf
    # fallback: se nada for encontrado (sem lances)
    legal = legal_moves(root, root.to_move)
    if not legal:
        return 0, None
    # embaralhe para não ficar determinístico quando empata
    random.shuffle(legal)
    # uma jogada "segura" inicial
    best_move = sorted(legal, key=lambda m: move_sort_key(root, m, for_player))[0]

    for depth in range(1, max_depth + 1):
        try:
            val, mv = alphabeta(root, depth, -math.inf, math.inf, for_player, deadline)
            if mv is not None:
                best_val, best_move = val, mv
        except Timeout:
            break
    return best_val, best_move

def alphabeta(st: State, depth: int, alpha: float, beta: float, max_player: int, deadline: float) -> Tuple[int, Optional[Tuple]]:
    if time.time() > deadline:
        raise Timeout()
    w = winner(st)
    if depth == 0 or terminal(st):
        return heuristic(st, max_player), None

    player = st.to_move
    moves = legal_moves(st, player)
    if not moves:
        return heuristic(st, max_player), None
    moves = sorted(moves, key=lambda m: move_sort_key(st, m, player))

    best_move: Optional[Tuple] = None
    if player == max_player:
        value = -math.inf
        for mv in moves:
            child = apply_move(st, mv)
            v, _ = alphabeta(child, depth - 1, alpha, beta, max_player, deadline)
            if v > value:
                value, best_move = v, mv
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return int(value), best_move
    else:
        value = math.inf
        for mv in moves:
            child = apply_move(st, mv)
            v, _ = alphabeta(child, depth - 1, alpha, beta, max_player, deadline)
            if v < value:
                value, best_move = v, mv
            beta = min(beta, value)
            if alpha >= beta:
                break
        return int(value), best_move

# ======= Interface de Terminal =======
def render_cell(st: State, rc: Coord) -> str:
    t = st.top(rc)
    if not t:
        return "__"
    owner = PLAYERS[t[0]]
    return f"{owner}{SIZE_LETTER[t[1]]}"

def print_board(st: State) -> None:
    print("\n   1   2   3")
    for r, row_label in enumerate("ABC"):
        cells = " | ".join(render_cell(st, (r, c)) for c in range(3))
        print(f"{row_label}  {cells}")
        if r < 2:
            print("  ---+---+---")
    hr = st.reserves[HUMAN]
    ar = st.reserves[AI]
    print(f"\nReservas H (Humano): G:{hr[3]} M:{hr[2]} P:{hr[1]}")
    print(f"Reservas I (IA)    : G:{ar[3]} M:{ar[2]} P:{ar[1]}")
    print()

def parse_command(s: str) -> Optional[Tuple[str, ...]]:
    parts = s.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()
    if cmd == "place" and len(parts) == 3:
        size = parts[1].upper()
        if size not in SIZE_MAP:
            return None
        rc = cell_name_to_coord(parts[2])
        if rc is None:
            return None
        return ("place", size, rc)
    if cmd == "move" and len(parts) == 3:
        src = cell_name_to_coord(parts[1])
        dst = cell_name_to_coord(parts[2])
        if src is None or dst is None:
            return None
        return ("move", src, dst)
    if cmd in ("help", "board", "quit"):
        return (cmd,)
    return None

def is_legal_command(st: State, cmd: Tuple[str, ...], player: int) -> bool:
    if cmd[0] == "place":
        _, sizeL, dst = cmd
        size = SIZE_MAP[sizeL]
        if st.reserves[player][size] <= 0:
            return False
        t = st.top(dst)
        return (t is None) or (t[1] < size)
    elif cmd[0] == "move":
        _, src, dst = cmd
        ts = st.top(src)
        if ts is None or ts[0] != player:
            return False
        t = st.top(dst)
        return (t is None) or (t[1] < ts[1])
    return True

def to_move_from_cmd(st: State, cmd: Tuple[str, ...]) -> Tuple:
    if cmd[0] == "place":
        _, sizeL, dst = cmd
        return ("place", SIZE_MAP[sizeL], dst)
    elif cmd[0] == "move":
        _, src, dst = cmd
        return ("move", src, dst)
    raise ValueError

def human_turn(st: State) -> State:
    print_board(st)
    while True:
        s = input("Sua jogada (ex.: 'place G B2' ou 'move A1 B1'; 'help' p/ ajuda): ").strip()
        cmd = parse_command(s)
        if not cmd:
            print("Comando inválido. Digite 'help' para exemplos.")
            continue
        if cmd[0] == "help":
            print("Comandos:")
            print("  place <P|M|G> <A1..C3>  → coloca peça da reserva")
            print("  move <orig> <dest>      → move peça visível do tabuleiro")
            print("  board                   → mostra o tabuleiro")
            print("  quit                    → abandonar")
            continue
        if cmd[0] == "board":
            print_board(st)
            continue
        if cmd[0] == "quit":
            print("Você desistiu. Vitória da IA.")
            sys.exit(0)
        if not is_legal_command(st, cmd, HUMAN):
            print("Jogada ilegal para você. Tente novamente.")
            continue
        mv = to_move_from_cmd(st, cmd)
        return apply_move(st, mv)

def ai_turn(st: State, time_limit: float = 30.0) -> State:
    print("\nIA pensando...")
    val, mv = minimax_iterative_deepening(st, AI, time_limit=time_limit, max_depth=12)
    if mv is None:
        # Sem jogadas: passa (empate ou posição terminal)
        print("IA não encontrou jogadas legais.")
        return st.copy()
    # Mostrar jogada em formato amigável
    if mv[0] == "place":
        _, size, dst = mv
        print(f"IA: place {SIZE_LETTER[size]} {coord_to_cell_name(dst)}  (valor {val})")
    else:
        _, src, dst = mv
        print(f"IA: move {coord_to_cell_name(src)} {coord_to_cell_name(dst)}  (valor {val})")
    return apply_move(st, mv)

def choose_start_player() -> int:
    while True:
        a = input("Quem começa? (h=humano, i=IA) [h/i]: ").strip().lower()
        if a in ("h", "humano", ""):
            return HUMAN
        if a in ("i", "ia"):
            return AI
        print("Opção inválida. Digite 'h' ou 'i'.")

def main():
    random.seed()  # desempates
    st = State()
    st.to_move = choose_start_player()
    st.history_tops.append(st.tops_signature())
    print("\nTamanhos: P=pequena, M=média, G=grande. Você é 'H', a IA é 'I'.")
    print_board(st)

    while True:
        if terminal(st):
            w = winner(st)
            print_board(st)
            if w is None:
                print("Empate.")
            elif w == HUMAN:
                print("Parabéns! Você venceu.")
            else:
                print("IA venceu.")
            return

        if st.to_move == HUMAN:
            st = human_turn(st)
        else:
            st = ai_turn(st, time_limit=30.0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaindo…")
