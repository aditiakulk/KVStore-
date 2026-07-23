cmake_minimum_required(VERSION 3.10)
project(kv_node)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -O2 so perf profiling reflects realistic performance, not debug-build noise.
# Add -g so perf can still resolve symbols/line numbers.
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -g -Wall -Wextra")

find_package(Threads REQUIRED)

add_executable(kv_node src/main.cpp)
target_link_libraries(kv_node PRIVATE Threads::Threads)
