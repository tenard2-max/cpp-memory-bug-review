#include <iostream>
#include <cstring>
#include <new>

// 초기화 오류 #4용 클래스 (생성자 멤버 미초기화)
struct BadDevice {
    int id;       // 초기화 안 됨
    bool active;  // 초기화 안 됨
    BadDevice() { /* 초기화 리스트 누락 */ }
};

// 초기화 오류 #8용 전역 객체 (정적 초기화 순서 문제)
extern int g_dependency;
struct GlobalA {
    int val;
    GlobalA();
};
struct GlobalB {
    int val;
    GlobalB() { val = g_dependency + 100; } // 미완료 전역 변수 참조
};

GlobalA objA;
int g_dependency = 42;
GlobalB objB;

GlobalA::GlobalA() { val = 10; }

// 메모리 오류 #5용 함수 (댕글링 포인터 반환)
int* get_dangling_pointer() {
    int stack_var = 99;
    return &stack_var; // 스택 주소 반환
}

// 메모리 오류 #10용 클래스 (얕은 복사로 인한 이중 해제)
class ShallowCopyClass {
public:
    int* ptr;
    ShallowCopyClass(int v) { ptr = new int(v); }
    ~ShallowCopyClass() { delete ptr; }
    // 복사 생성자를 구현하지 않아 기본 얕은 복사(Shallow Copy) 발생
};

void trigger_all_20_errors() {
    // ==========================================
    // [파트 1: 초기화 오류 10가지 (활성화)]
    // ==========================================

    // 1. 미초기화 지역 변수 사용 (쓰레기 값 읽기)
    int uninit_local;
    volatile int val1 = uninit_local + 1;

    // 2. 와일드 포인터(미초기화 포인터) 역참조
    int* wild_ptr;
    volatile int val2 = *wild_ptr;

    // 3. 참조자 대상의 널 포인터 역참조 우회 초기화
    int* null_for_ref = nullptr;
    int& bad_ref = *null_for_ref; 
    volatile int val3 = bad_ref;

    // 4. 생성자에서 멤버 미초기화된 객체 사용
    BadDevice dev;
    volatile int val4 = dev.id;

    // 5. 동적 할당 후 부분 초기화된 배열의 미정의 요소 읽기
    int* dyn_arr = new int[10];
    dyn_arr[0] = 1;
    volatile int val5 = dyn_arr[5]; 
    delete[] dyn_arr;

    // 6. 미초기화된 변수를 함수 인자로 전달
    auto lambda = [](int x) { return x * 2; };
    int uninit_arg;
    volatile int val6 = lambda(uninit_arg);

    // 7. 조건부 초기화 누락 변수 사용
    int cond_var;
    bool flag = false;
    if (flag) {
        cond_var = 100;
    }
    volatile int val7 = cond_var;

    // 8. 정적 초기화 순서 문제(Static Initialization Order Fiasco)로 인한 잘못된 값 참조
    volatile int val8 = objB.val;

    // 9. 미초기화 불리언 플래그 제어 흐름 사용
    bool uninit_flag;
    volatile int val9 = uninit_flag ? 1 : 0;

    // 10. 구조체 패딩 바이트 미초기화 상태 memcmp 수행
    struct PaddingTest {
        char c;
        int i; // 패딩 바이트 발생
    };
    PaddingTest pt1{}, pt2{};
    pt1.c = 'a'; pt1.i = 10;
    pt2.c = 'a'; pt2.i = 10;
    volatile int val10 = std::memcmp(&pt1, &pt2, sizeof(PaddingTest));


    // ==========================================
    // [파트 2: 메모리 오류 10가지 (활성화)]
    // ==========================================

    // 1. 메모리 누수 (Memory Leak)
    int* leak_ptr = new int(500);
    // delete leak_ptr; 누락됨

    // 2. 이중 해제 (Double Free)
    int* double_ptr = new int(100);
    delete double_ptr;
    delete double_ptr; // 두 번째 해제

    // 3. 잘못된 해제 연산자 매칭 (Mismatched Deallocation)
    int* mismatch_ptr = new int;
    delete[] mismatch_ptr; // 단일 객체에 delete[] 사용

    // 4. 해제 후 사용 (Use-After-Free)
    int* uaf_ptr = new int(300);
    delete uaf_ptr;
    volatile int val_uaf = *uaf_ptr; // 해제된 영역 접근

    // 5. 댕글링 포인터 역참조 (Dangling Pointer)
    int* dang_ptr = get_dangling_pointer();
    volatile int val_dang = *dang_ptr;

    // 6. 힙 버퍼 오버플로우 (Heap Buffer Overflow)
    int* heap_buf = new int[5];
    heap_buf[5] = 999; // 할당된 크기(5)를 넘어선 영역에 쓰기
    delete[] heap_buf;

    // 7. 스택 버퍼 오버플로우 (Stack Buffer Overflow)
    int stack_buf[3];
    stack_buf[5] = 777; // 스택 경계 초과 쓰기

    // 8. 널 포인터 역참조 (Null Pointer Dereference)
    int* null_ptr = nullptr;
    volatile int val_null = *null_ptr;

    // 9. 자원 고갈 시 예외 처리 누락 대규모 할당 (Out of Memory)
    int* huge_mem = new int[2000000000]; // 대규모 메모리 요청
    delete[] huge_mem;

    // 10. 얕은 복사(Shallow Copy)로 인한 이중 해제
    ShallowCopyClass obj1(10);
    {
        ShallowCopyClass obj2 = obj1; // 얕은 복사로 동일한 포인터 공유
    } // obj2 소멸 시 delete 발생 -> 이후 obj1 소멸 시 이미 해제된 포인터를 또 delete (Double Free)
}

int main() {
    std::cout << "모든 오류 트리거 실행 시작..." << std::endl;
    trigger_all_20_errors();
    std::cout << "실행 종료." << std::endl;
    return 0;
}