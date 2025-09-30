#include <iostream>
#include <vector>
#include <algorithm>

#include <tbb/tbb.h>
#include "oneapi/tbb/blocked_range.h"
#include "oneapi/tbb/parallel_for.h"

using namespace std;
using namespace oneapi;

void ParallelSaxpy(float a, float x[],  float y[], float z[], int n)
{
    tbb::parallel_for(
        tbb::blocked_range<int>(0, n),

        // lambda function
        [&](tbb::blocked_range<int> r) {
            for (auto i = r.begin(); i != r.end(); i++) {
                z[i] = a * x[i] + y[i];
            }
        }

        );
}

int main(){

	int size = 1000;
    static vector<float> x(size);
    static vector<float> y(size);
    static vector<float> out(size);
    float a = 2.1;

    generate(x.begin(), x.end(), rand);
    generate(y.begin(), y.end(), rand);

	tbb::tick_count t0 = tbb::tick_count::now();
 	ParallelSaxpy(a, &x[0], &y[0], &out[0], x.size());
 	
 	cout << "Time: " << (tbb::tick_count::now()-t0).seconds() << "seconds" << endl;

 	return 0;

 }
