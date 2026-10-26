#include <cstdlib>

int main() {
    int* value = static_cast<int*>(std::malloc(sizeof(int)));
    if (value == nullptr) {
        return 1;
    }
    *value = 1;
    std::free(value);
    *value = 2;
    return 0;
}
