## 버그 종류
미초기화 지역 변수 사용

## 키워드
uninit_local, volatile, 초기화

## 문제 코드
```c
// 1. 미초기화 지역 변수 사용 (쓰레기 값 읽기)
int uninit_local;
volatile int val1 = uninit_local + 1;
```

## 수정 코드
```c
int uninit_local = 0;
volatile int val1 = uninit_local + 1;
```

## 해설
int uninit_local; 선언 후 초기화 없이 uninit_local + 1 읽기 연산을 수행한다. 쓰레기 값 읽기로 UB다.

## 오탐 방지
아니오

---

## 버그 종류
와일드 포인터 역참조

## 키워드
wild_ptr, 포인터, 역참조

## 문제 코드
```c
// 2. 와일드 포인터(미초기화 포인터) 역참조
int* wild_ptr;
volatile int val2 = *wild_ptr;
```

## 수정 코드
```c
int value = 0;
int* wild_ptr = &value;
volatile int val2 = *wild_ptr;
```

## 해설
int* wild_ptr; 주소 할당 없이 *wild_ptr 역참조를 수행한다. 와일드 포인터 접근으로 UB·크래시 위험이 있다.

## 오탐 방지
아니오

---

## 버그 종류
스택 버퍼 오버플로우 (sprintf)

## 키워드
sprintf, ssTemp, 버퍼

## 문제 코드
```c
// 3. 스택 버퍼 오버플로우
char ssTemp[10];
sprintf(ssTemp, "dfsljsdlkfjsldkfdlfksldkfsjlfd");
```

## 수정 코드
```c
char ssTemp[10];
snprintf(ssTemp, sizeof(ssTemp), "dfsljsdlkfjsldkfdlfksldkfsjlfd");
```

## 해설
10바이트 배열 ssTemp[10]에 긴 문자열을 sprintf로 복사한다. 널 포함 길이가 버퍼를 초과해 스택을 침범한다.

## 오탐 방지
아니오

---

## 버그 종류
스택 버퍼 오버플로우 (memcpy)

## 키워드
memcpy, ssTemp, 버퍼

## 문제 코드
```c
// 4. 스택 버퍼 오버플로우
char ssTemp[10];
memcpy(ssTemp, "dlfkjsdklfjdslfksdjl", 11);
```

## 수정 코드
```c
char ssTemp[10];
memcpy(ssTemp, "dlfkjsdklfjdslfksdjl", sizeof(ssTemp));
ssTemp[sizeof(ssTemp) - 1] = '\0';
```

## 해설
10바이트 배열 ssTemp[10]에 memcpy(..., 11)로 11바이트를 복사한다. 1바이트 초과로 스택 버퍼 오버플로우다.

## 오탐 방지
아니오

---

## 버그 종류
스택 버퍼 오버플로우 (strcat)

## 키워드
sprintf, strcat, ssTemp

## 문제 코드
```c
// 5. 스택 버퍼 오버플로우
char ssTemp[10];
sprintf(ssTemp, "123456789");
strcat(ssTemp, "1234");
```

## 수정 코드
```c
char ssTemp[10];
snprintf(ssTemp, sizeof(ssTemp), "123456789");
strncat(ssTemp, "1234", sizeof(ssTemp) - strlen(ssTemp) - 1);
```

## 해설
sprintf로 10바이트를 채운 뒤 strcat로 4바이트를 추가한다. 총 길이가 버퍼를 넘어 4바이트 초과 스택 오버플로우다.

## 오탐 방지
아니오

---

## 버그 종류
동적 배열 미초기화 요소 읽기

## 키워드
new, dyn_arr, 초기화

## 문제 코드
```c
// 6. 동적 할당 후 부분 초기화된 배열의 미정의 요소 읽기
int* dyn_arr = new int[10];
dyn_arr[0] = 1;
volatile int val5 = dyn_arr[5];
delete[] dyn_arr;
```

## 수정 코드
```c
int* dyn_arr = new int[10]();
dyn_arr[0] = 1;
volatile int val5 = dyn_arr[5];
delete[] dyn_arr;
```

## 해설
new int[10] 할당 후 dyn_arr[0]만 초기화하고 쓰레기 값이 들어 있는 dyn_arr[5]를 읽는다.

## 오탐 방지
아니오

---

## 버그 종류
조건부 초기화 누락 변수 사용

## 키워드
cond_var, flag, 초기화

## 문제 코드
```c
// 7. 조건부 초기화 누락 변수 사용
int cond_var;
bool flag = false;
if (flag) {
    cond_var = 100;
}
volatile int val7 = cond_var;
```

## 수정 코드
```c
int cond_var = 0;
bool flag = false;
if (flag) {
    cond_var = 100;
}
volatile int val7 = cond_var;
```

## 해설
flag가 false이므로 cond_var가 초기화되지 않은 상태로 val7에 대입된다. 조건부 초기화 누락 UB다.

## 오탐 방지
아니오

---

## 버그 종류
미초기화 불리언 플래그 사용

## 키워드
uninit_flag, bool, 삼항

## 문제 코드
```c
// 8. 미초기화 불리언 플래그 제어 흐름 사용
bool uninit_flag;
volatile int val9 = uninit_flag ? 1 : 0;
```

## 수정 코드
```c
bool uninit_flag = false;
volatile int val9 = uninit_flag ? 1 : 0;
```

## 해설
bool uninit_flag; 초기화 없이 삼항 연산자 조건식으로 사용한다. 미초기화 bool 읽기 UB다.

## 오탐 방지
아니오

---

## 버그 종류
메모리 누수

## 키워드
new, leak_ptr, delete, leak

## 문제 코드
```c
// 9. 메모리 누수 (Memory Leak)
int* leak_ptr = new int(500);
// delete leak_ptr; 누락됨
```

## 수정 코드
```c
int* leak_ptr = new int(500);
delete leak_ptr;
leak_ptr = 0;
```

## 해설
int* leak_ptr = new int(500); 동적 할당 후 delete가 누락되어 메모리 누수가 난다.

## 오탐 방지
아니오

---

## 버그 종류
이중 해제 Double Free

## 키워드
delete, double_ptr, Double Free

## 문제 코드
```c
// 10. 이중 해제 (Double Free)
int* double_ptr = new int(100);
delete double_ptr;
delete double_ptr;
```

## 수정 코드
```c
int* double_ptr = new int(100);
delete double_ptr;
double_ptr = 0;
```

## 해설
delete double_ptr; 실행 후 동일 포인터를 다시 해제한다. Double Free로 힙 손상·크래시 위험이 있다.

## 오탐 방지
아니오

---

## 버그 종류
힙 버퍼 오버플로우

## 키워드
new, heap_buf, 오버플로우

## 문제 코드
```c
// 11. 힙 버퍼 오버플로우 (Heap Buffer Overflow)
int* heap_buf = new int[5];
heap_buf[5] = 999;
delete[] heap_buf;
```

## 수정 코드
```c
int* heap_buf = new int[5];
heap_buf[4] = 999;
delete[] heap_buf;
```

## 해설
new int[5](인덱스 0~4) 할당 후 범위를 벗어난 heap_buf[5]에 쓴다. 힙 버퍼 오버플로우다.

## 오탐 방지
아니오

---

## 버그 종류
스택 버퍼 오버플로우 (배열 경계)

## 키워드
stack_buf, 오버플로우, 스택

## 문제 코드
```c
// 12. 스택 버퍼 오버플로우 (Stack Buffer Overflow)
int stack_buf[3];
stack_buf[5] = 777;
```

## 수정 코드
```c
int stack_buf[3] = {0};
stack_buf[2] = 777;
```

## 해설
int stack_buf[3](인덱스 0~2) 선언 후 범위를 벗어난 stack_buf[5]에 쓴다. 스택 버퍼 오버플로우다.

## 오탐 방지
아니오
