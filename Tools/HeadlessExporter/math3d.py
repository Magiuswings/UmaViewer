"""Small row-major Unity TRS / bind-matrix helpers without a NumPy dependency."""
import math

IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]

def multiply(a, b):
    return [sum(a[r*4+k] * b[k*4+c] for k in range(4)) for r in range(4) for c in range(4)]

def inverse(m):
    rows = [list(m[r*4:r*4+4]) + IDENTITY[r*4:r*4+4] for r in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(rows[row][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise ValueError("Singular matrix")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        value = rows[col][col]
        rows[col] = [v / value for v in rows[col]]
        for row in range(4):
            if row != col:
                value = rows[row][col]
                rows[row] = [a-value*b for a,b in zip(rows[row], rows[col])]
    return [v for row in rows for v in row[4:]]

def components(value, count=3):
    if isinstance(value, (list, tuple)):
        return list(value[:count])
    keys = ("x", "y", "z", "w")
    if isinstance(value, dict):
        return [value[k] for k in keys[:count]]
    return [getattr(value, k) for k in keys[:count]]

def trs(position, rotation, scale):
    x,y,z,w = components(rotation, 4)
    norm = math.sqrt(x*x+y*y+z*z+w*w)
    x,y,z,w = x/norm,y/norm,z/norm,w/norm
    sx,sy,sz = components(scale)
    px,py,pz = components(position)
    return [(1-2*(y*y+z*z))*sx, 2*(x*y-z*w)*sy, 2*(x*z+y*w)*sz, px,
            2*(x*y+z*w)*sx, (1-2*(x*x+z*z))*sy, 2*(y*z-x*w)*sz, py,
            2*(x*z-y*w)*sx, 2*(y*z+x*w)*sy, (1-2*(x*x+y*y))*sz, pz,
            0,0,0,1]

def unity_matrix(value):
    return [value[f"e{r}{c}"] if isinstance(value, dict) else getattr(value,f"e{r}{c}") for r in range(4) for c in range(4)]

def transform(m, value, direction=False):
    xyz = components(value)
    return [sum(m[r*4+c]*xyz[c] for c in range(3)) + (0 if direction else m[r*4+3]) for r in range(3)]

def vec(value):
    a = list(value)
    return dict(zip(("x","y","z","w"), a + [0.]*(4-len(a))))

def normal(m, value):
    inv = inverse(m)
    xyz = components(value)
    n = [sum(inv[c*4+r]*xyz[c] for c in range(3)) for r in range(3)]
    length = math.sqrt(sum(v*v for v in n))
    return vec([v/length for v in n] if length else [0,0,0])
