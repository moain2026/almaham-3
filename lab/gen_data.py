"""Pre-generate synthetic line dataset (uint8 [N,48,192]) in parallel."""
import sys, random, numpy as np
from multiprocessing import Pool
import synth
from prep import to_input
def work(args):
    seed, n = args; random.seed(seed); np.random.seed(seed)
    X = np.zeros((n, 48, 192), np.uint8); Y = []
    for i in range(n):
        im, lab = synth.sample(); X[i] = (to_input(im)[0] * 255).astype(np.uint8); Y.append(lab)
    return X, Y
if __name__ == "__main__":
    N, out, base = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    chunks = [(base + i, N // 16) for i in range(16)]
    with Pool(4) as p: res = p.map(work, chunks)
    X = np.concatenate([r[0] for r in res]); Y = [y for r in res for y in r[1]]
    np.savez(out, X=X, Y=np.array(Y))
    print(X.shape)
