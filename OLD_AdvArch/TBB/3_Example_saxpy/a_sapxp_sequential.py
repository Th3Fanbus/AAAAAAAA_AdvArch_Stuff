import time
import random

def run_saxpy(x,y,a):
	out = []
	# out = [0]*len(x)
	for i in range(len(x)):
		out.append((x[i]+y[i])*a)
		# out[i] = (x[i]+y[i])*a
	return out

if __name__ == "__main__":
	size = 100000000
	a = 2.1
	
	print(".")
	x = [random.random() for i in range(size)]
	y = [random.random() for i in range(size)]

	print("..")
	start = time.time()
	out = run_saxpy(x,y,a)
	end = (time.time()-start)
	print(out[:5])
	print("Total time: %0.10f ms"%end)
