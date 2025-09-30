import numpy as np
import time
from numba import jit

@jit(nopython=True,parallel=True)
def run_saxpy(x,y,a):
	return a*(x+y)

if __name__ == "__main__":
	size = 10000000000
	a = 2.1
	
	print(".")
	x = np.random.random(size)
	y = np.random.random(size)

	print("..")
	start = time.time()
	out = run_saxpy(x,y,a)
	end = (time.time()-start)
	
	print(out[:5])
	print("Total time: %0.10f ms"%end)
