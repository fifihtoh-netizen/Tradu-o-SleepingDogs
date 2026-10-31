#!/usr/bin/env python3
"""
Gera um UI.big traduzido com EXATAMENTE o mesmo tamanho do UI.big original
(o launcher do port Android confere o tamanho) e o UI.bix correspondente.

Uso:
  python build_ui_big.py UI.big UI.bix UI_traduzido.big UI_traduzido.bix SAIDA_UI.big SAIDA_UI.bix

Entradas : UI.big/UI.bix originais (do port) + par da traducao (TriboGamer)
Saidas   : SAIDA_UI.big (mesmo tamanho do original) e SAIDA_UI.bix

Como funciona (formato deduzido por engenharia reversa):
 - O .bix tem registros de 24 bytes (comecando no byte 5). Em cada registro:
     bytes 0..2  = offset da entrada no .big, em unidades de 1 KB
     bytes 15..18 = tamanho da entrada em bytes (cabecalho de 16 bytes incluso)
 - Cada entrada no .big comeca com [magic 4B][tam-16 4B][tam-16 4B][4B zero].
 - A traducao nao mexe no miolo do .big: ela anexa as entradas novas no final e
   aponta o .bix para la (por isso o arquivo cresce). Aqui as entradas novas
   voltam para dentro do arquivo original, no lugar das antigas. Se uma entrada
   nova for maior que o espaco antigo, entradas pequenas vizinhas sao movidas
   para sobras livres do arquivo para abrir espaco.
"""
import os
import sys
import struct
import hashlib
import numpy as np

PH, STRIDE = 5, 24
KB = 1024


def u24(d, q):
    return d[q] | d[q + 1] << 8 | d[q + 2] << 16


def u32(d, q):
    return struct.unpack_from('<I', d, q)[0]


def ceil_kb(n):
    return (n + KB - 1) // KB


def hdr_ok(mm, B, L):
    off = B * KB
    if off + 16 > len(mm):
        return False
    h = bytes(mm[off:off + 16])
    s1, s2 = struct.unpack_from('<II', h, 4)
    return s1 == L - 16 and s2 == L - 16


def main(orig_big, orig_bix, trad_big, trad_bix, out_big, out_bix):
    a = open(orig_bix, 'rb').read()
    b = bytearray(open(trad_bix, 'rb').read())
    assert len(a) == len(b), "os dois .bix deveriam ter o mesmo tamanho"
    SIZE = os.path.getsize(orig_big)
    assert SIZE % KB == 0
    END = SIZE // KB
    big = np.memmap(orig_big, dtype=np.uint8, mode='r')
    tbig = np.memmap(trad_big, dtype=np.uint8, mode='r')
    assert len(tbig) > SIZE and bytes(tbig[:SIZE:4096]) == bytes(big[::4096]), \
        "o .big traduzido deveria comecar igual ao original"

    # ---- entradas do original --------------------------------------------
    by_b = {}
    for q in range(PH, len(a) - STRIDE, STRIDE):
        B, L = u24(a, q), u32(a, q + 15)
        if 0 < B < END and 16 <= L < (1 << 26):
            by_b.setdefault(B, set()).add(L)
    Bs = sorted(by_b)
    ent = {}  # B -> dict(L, ok, ext)
    for i, B in enumerate(Bs):
        nxt = Bs[i + 1] if i + 1 < len(Bs) else END
        Ls = by_b[B]
        ok = len(Ls) == 1 and hdr_ok(big, B, next(iter(Ls)))
        if ok:
            L = next(iter(Ls))
            ext = min(ceil_kb(L), nxt - B)
        else:
            L, ext = None, nxt - B
        ent[B] = dict(L=L, ok=ok, ext=ext)

    owner = np.full(END, -1, dtype=np.int64)  # B dono de cada KB
    for B, e in ent.items():
        owner[B:B + e['ext']] = B

    # ---- registros traduzidos --------------------------------------------
    T = []
    for q in range(PH, len(a) - STRIDE, STRIDE):
        Bt = u24(b, q)
        if Bt >= END and Bt * KB < len(tbig):
            Bo = u24(a, q)
            Lt = u32(b, q + 15)
            assert Bo in ent, f"registro {q}: entrada original desconhecida"
            assert hdr_ok(tbig, Bt, Lt), f"registro {q}: cabecalho traduzido invalido"
            T.append(dict(q=q, Bo=Bo, Bt=Bt, Lt=Lt, need=ceil_kb(Lt)))
    print("entradas traduzidas:", len(T))
    tb = [t['Bo'] for t in T]
    assert len(set(tb)) == len(tb), "duas entradas traduzidas apontam para o mesmo original"
    Tset = set(tb)

    free = owner < 0
    # libera os espacos antigos das entradas substituidas
    for t in T:
        e = ent[t['Bo']]
        owner[t['Bo']:t['Bo'] + e['ext']] = -1
    free = owner < 0

    place = {}   # q -> B novo
    moved = {}   # B antigo -> B novo (entradas originais movidas)
    vacated = []  # (B, ext) de intervalos antigos esvaziados

    def run_free(s, n):
        return s >= 0 and s + n <= END and free[s:s + n].all()

    deferred = []
    for t in sorted(T, key=lambda x: x['Bo']):
        if run_free(t['Bo'], t['need']):
            place[t['q']] = t['Bo']
            free[t['Bo']:t['Bo'] + t['need']] = False
            owner[t['Bo']:t['Bo'] + t['need']] = -2 - t['Bo']  # reservado
        else:
            deferred.append(t)
    print("cabem no lugar original:", len(place), "| precisam de espaco extra:", len(deferred))

    def find_run(n, exclude=None):
        """melhor encaixe: menor corrida livre >= n (fora de 'exclude')."""
        f = free.copy()
        if exclude:
            f[exclude[0]:exclude[1]] = False
        d = np.diff(np.concatenate(([0], f.astype(np.int8), [0])))
        starts = np.nonzero(d == 1)[0]
        ends = np.nonzero(d == -1)[0]
        lens = ends - starts
        ok = lens >= n
        if not ok.any():
            return None
        idx = np.nonzero(ok)[0]
        best = idx[np.argmin(lens[idx])]
        return int(starts[best])

    def movable(B):
        e = ent.get(B)
        return e is not None and e['ok'] and B not in Tset and B not in moved

    for t in sorted(deferred, key=lambda x: -x['need']):
        need = t['need']
        mv = np.zeros(END + 1, dtype=bool)
        for B in ent:
            if movable(B):
                mv[B] = True
        occupied = owner >= 0
        movable_cell = occupied & mv[np.clip(owner, 0, END)]
        blocked = (owner < -1) | (occupied & ~movable_cell)
        cb = np.concatenate(([0], np.cumsum(blocked)))
        co = np.concatenate(([0], np.cumsum(occupied)))
        starts = np.arange(0, END - need + 1)
        nblk = cb[starts + need] - cb[starts]
        cost_arr = co[starts + need] - co[starts]
        valid = nblk == 0
        assert valid.any(), f"sem janela para o registro {t['q']} (precisa de {need} KB)"
        score = np.where(valid, cost_arr * 1_000_000 + np.abs(starts - t['Bo']), np.iinfo(np.int64).max)
        s = int(np.argmin(score))
        occ = set(int(x) for x in np.unique(owner[s:s + need]) if x >= 0)
        best = (int(cost_arr[s]), s, occ)
        cost, s, occ = best
        win = (s, s + need)
        # tira as entradas da janela e as realoca fora dela
        for B in sorted(occ):
            e = ent[B]
            owner[B:B + e['ext']] = -1
            free[B:B + e['ext']] = True
        for B in sorted(occ, key=lambda x: -ent[x]['ext']):
            e = ent[B]
            n = ceil_kb(e['L'])
            dst = find_run(n, exclude=win)
            assert dst is not None, "sem espaco livre para realocar uma entrada"
            moved[B] = dst
            vacated.append((B, e['ext']))
            free[dst:dst + n] = False
            owner[dst:dst + n] = -2 - dst
        place[t['q']] = s
        free[s:s + need] = False
        owner[s:s + need] = -2 - s
        print(f"  registro {t['q']}: {need} KB em {s} (movidas {len(occ)} entradas, {cost} KB)")

    # ---- monta a saida ----------------------------------------------------
    print("escrevendo", out_big)
    with open(orig_big, 'rb') as fi, open(out_big, 'wb') as fo:
        while True:
            chunk = fi.read(8 << 20)
            if not chunk:
                break
            fo.write(chunk)
    mm = np.memmap(out_big, dtype=np.uint8, mode='r+')
    # zera o que ficou vago (entradas substituidas e entradas movidas)
    for t in T:
        e = ent[t['Bo']]
        mm[t['Bo'] * KB:(t['Bo'] + e['ext']) * KB] = 0
    for B, ext in vacated:
        mm[B * KB:(B + ext) * KB] = 0
    # grava entradas movidas (origem = arquivo original intacto)
    for B, dst in moved.items():
        L = ent[B]['L']
        mm[dst * KB:dst * KB + L] = big[B * KB:B * KB + L]
    # grava entradas traduzidas
    for t in T:
        d = place[t['q']]
        mm[d * KB:d * KB + t['Lt']] = tbig[t['Bt'] * KB:t['Bt'] * KB + t['Lt']]
    mm.flush()

    # ---- atualiza o .bix ---------------------------------------------------
    nb = bytearray(b)
    for t in T:
        d = place[t['q']]
        nb[t['q']:t['q'] + 3] = struct.pack('<I', d)[:3]
    patched = 0
    for q in range(PH, len(nb) - STRIDE, STRIDE):
        B = u24(nb, q)
        if B in moved and u32(nb, q + 15) == ent[B]['L'] and nb[q + 3:q + 8] == b'\0' * 5 \
                and q not in place:
            nb[q:q + 3] = struct.pack('<I', moved[B])[:3]
            patched += 1
    open(out_bix, 'wb').write(nb)
    print("registros de entradas movidas atualizados:", patched, "de", len(moved), "entradas")

    # ---- verificacao ---------------------------------------------------------
    print("verificando...")
    assert os.path.getsize(out_big) == SIZE
    out = np.memmap(out_big, dtype=np.uint8, mode='r')
    for t in T:
        d = place[t['q']]
        assert u24(nb, t['q']) == d
        assert bytes(out[d * KB:d * KB + t['Lt']]) == bytes(tbig[t['Bt'] * KB:t['Bt'] * KB + t['Lt']])
    bad = 0
    for q in range(PH, len(nb) - STRIDE, STRIDE):
        B, L = u24(nb, q), u32(nb, q + 15)
        if 0 < B < END and 16 <= L < (1 << 26) and q not in place:
            o = u24(a, q)
            if o in ent and ent[o]['ok'] and ent[o]['L'] == L:
                if not hdr_ok(out, B, L):
                    bad += 1
    print("registros nao-traduzidos com cabecalho invalido na saida:", bad)
    assert bad == 0
    print("tamanho final:", os.path.getsize(out_big), "(original:", SIZE, ")")
    for f in (out_big, out_bix):
        h = hashlib.md5()
        with open(f, 'rb') as fh:
            for c in iter(lambda: fh.read(8 << 20), b''):
                h.update(c)
        print("md5", os.path.basename(f), h.hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 7:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:])
