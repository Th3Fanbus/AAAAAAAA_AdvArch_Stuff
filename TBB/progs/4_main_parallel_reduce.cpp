#include <oneapi/tbb/info.h>
#include <oneapi/tbb/parallel_for.h>
#include <oneapi/tbb/task_arena.h>
#include <oneapi/tbb/parallel_reduce.h>
#include <cassert>
#include <iostream>

// https://docs.oneapi.io/versions/latest/onetbb/tbb_userguide/Migration_Guide/Task_Scheduler_Init.html

int main() {
    // Get the default number of threads
    int num_threads = oneapi::tbb::info::default_concurrency();
    std::cout << "Default concurrency " << num_threads << std::endl;

    int sum = oneapi::tbb::parallel_reduce(oneapi::tbb::blocked_range<int>(1,101), 0,
        [](oneapi::tbb::blocked_range<int> const& r, int init) -> int {
          std::cout << "R.B:" << r.begin() << "\tR.E:" << r.end() << std::endl;  
          for (int v = r.begin(); v != r.end(); v++  ) {
             init += v;
          }
          return init;
        },
        [](int lhs, int rhs) -> int {
          return lhs + rhs;
        }
    );

    std::cout << "Sum " << sum << std::endl;
    return 0;
}
