#include <oneapi/tbb/info.h>
#include <oneapi/tbb/parallel_for.h>
#include <cassert>
#include <iostream>
#include <cmath>
#include <vector>

// using namespace oneapi;

int main() {
    // Get the default number of threads
    int num_threads = oneapi::tbb::info::default_concurrency();
    std::cout << "Default concurrency " << num_threads << std::endl;

    auto values = std::vector<double>(10000);

    oneapi::tbb::parallel_for(
        oneapi::tbb::blocked_range<int>(0,values.size()),
        [&](tbb::blocked_range<int> r){
            for (int i=r.begin(); i<r.end(); i++){
                values[i] = std::sin(i * 0.001);
            }
        }
    );

    double total = 0;
    for (double value : values){
        total += value;
    }
    
    std::cout << "Total " << total << std::endl;
    return 0;
}
