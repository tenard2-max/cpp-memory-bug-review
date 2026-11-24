#include <iostream>
#include <cstring>
#include <new>




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

		// 3~5. 메모리
    char ssTemp[10];
    sprintf(ssTemp, "dfsljsdlkfjsldkfdlfksldkfsjlfd");
		
		memcpy( ssTemp, "dlfkjsdklfjdslfksdjl", 11);
		
		sprintf(ssTemp, "123456789");
		strcat(ssTemp, "1234");
		
    

    // 6. 동적 할당 후 부분 초기화된 배열의 미정의 요소 읽기
    int* dyn_arr = new int[10];
    dyn_arr[0] = 1;
    volatile int val5 = dyn_arr[5]; 
    delete[] dyn_arr;

    
    // 7. 조건부 초기화 누락 변수 사용
    int cond_var;
    bool flag = false;
    if (flag) {
        cond_var = 100;
    }
    volatile int val7 = cond_var;

    

    // 8. 미초기화 불리언 플래그 제어 흐름 사용
    bool uninit_flag;
    volatile int val9 = uninit_flag ? 1 : 0;

   

    // ==========================================
    // [파트 2: 메모리 오류 10가지 (활성화)]
    // ==========================================

    // 9. 메모리 누수 (Memory Leak)
    int* leak_ptr = new int(500);
    // delete leak_ptr; 누락됨

    // 10. 이중 해제 (Double Free)
    int* double_ptr = new int(100);
    delete double_ptr;
    delete double_ptr; // 두 번째 해제

   
    
    // 11. 힙 버퍼 오버플로우 (Heap Buffer Overflow)
    int* heap_buf = new int[5];
    heap_buf[5] = 999; // 할당된 크기(5)를 넘어선 영역에 쓰기
    delete[] heap_buf;

    // 12. 스택 버퍼 오버플로우 (Stack Buffer Overflow)
    int stack_buf[3];
    stack_buf[5] = 777; // 스택 경계 초과 쓰기

    
   
}

int main() {
    std::cout << "모든 오류 트리거 실행 시작..." << std::endl;
    trigger_all_20_errors();
    std::cout << "실행 종료." << std::endl;
    return 0;
}