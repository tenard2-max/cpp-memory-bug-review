#include <iostream>
#include <cstring>
#include <new>

// sample2: 원본 대비 약 4배 길이. 오류 1~12는 trigger_all_20_errors에 원본 그대로 유지.
// 길이만 늘리기 위한 주석 패딩(아래). filler 함수/포인터 선언은 넣지 않음
// → 분석 창이 쪼개지거나 희석되지 않게 함.
//
// PAD 001 ATM device inventory and cassette status checkpoints for long-file review
// PAD 002 host message types heartbeat reconnect backoff and settlement file rotate
// PAD 003 pinpad encrypt session key timeout and key-echo disabled operator path
// PAD 004 receipt presenter wait cut feed linedata and journal append flush close
// PAD 005 network link monitor keepalive collision handle and advice reverse path
// PAD 006 emv aid candidate list cvm rules terminal risk and contactless tap poll
// PAD 007 ui idle menu amount confirm processing success fail and retry screens
// PAD 008 config schema migrate default load save and digest verify after download
// PAD 009 watchdog kick timeout dump stack service ticket and power-fail recover
// PAD 010 maintenance diagnose calibrate firmware query and nvram checksum validate
// PAD 011 audit trail role privilege elevate deny session expire and local deny list
// PAD 012 cash unit OK LOW EMPTY JAM door sensor vault flag and reject-bin nearfull
// PAD 013 host approve decline referral capture reverse and settlement archive path
// PAD 014 log rotate compress upload schedule debug info warn error channels
// PAD 015 sample2 goal: keep twelve intentional bugs dense inside one trigger function
// PAD 016 do not add memset memcpy sprintf new delete into padding region at all
// PAD 017 sliding window and prune behavior must still see trigger_all_20_errors whole
// PAD 018 long file regression for RAG few-shot injection under larger source context
// PAD 019 measure finding count vs original short sample under same model settings
// PAD 020 end of narrative padding block before executable trigger function begins
// PAD 021 secondary notes for operators reviewing oversized sources in offline lab
// PAD 022 CDU SPR PIN CAM RCPT modules are referenced only as documentation tokens
// PAD 023 transaction flow card read pin entry limit check dispense and journalize
// PAD 024 no additional functions here on purpose to avoid depth-1 brace false chunks
// PAD 025 continue padding lines to approach four times original sample line count
// PAD 026 continue padding lines to approach four times original sample line count
// PAD 027 continue padding lines to approach four times original sample line count
// PAD 028 continue padding lines to approach four times original sample line count
// PAD 029 continue padding lines to approach four times original sample line count
// PAD 030 continue padding lines to approach four times original sample line count
// PAD 031 continue padding lines to approach four times original sample line count
// PAD 032 continue padding lines to approach four times original sample line count
// PAD 033 continue padding lines to approach four times original sample line count
// PAD 034 continue padding lines to approach four times original sample line count
// PAD 035 continue padding lines to approach four times original sample line count
// PAD 036 continue padding lines to approach four times original sample line count
// PAD 037 continue padding lines to approach four times original sample line count
// PAD 038 continue padding lines to approach four times original sample line count
// PAD 039 continue padding lines to approach four times original sample line count
// PAD 040 continue padding lines to approach four times original sample line count
// PAD 041 continue padding lines to approach four times original sample line count
// PAD 042 continue padding lines to approach four times original sample line count
// PAD 043 continue padding lines to approach four times original sample line count
// PAD 044 continue padding lines to approach four times original sample line count
// PAD 045 continue padding lines to approach four times original sample line count
// PAD 046 continue padding lines to approach four times original sample line count
// PAD 047 continue padding lines to approach four times original sample line count
// PAD 048 continue padding lines to approach four times original sample line count
// PAD 049 continue padding lines to approach four times original sample line count
// PAD 050 continue padding lines to approach four times original sample line count
// PAD 051 continue padding lines to approach four times original sample line count
// PAD 052 continue padding lines to approach four times original sample line count
// PAD 053 continue padding lines to approach four times original sample line count
// PAD 054 continue padding lines to approach four times original sample line count
// PAD 055 continue padding lines to approach four times original sample line count
// PAD 056 continue padding lines to approach four times original sample line count
// PAD 057 continue padding lines to approach four times original sample line count
// PAD 058 continue padding lines to approach four times original sample line count
// PAD 059 continue padding lines to approach four times original sample line count
// PAD 060 continue padding lines to approach four times original sample line count
// PAD 061 continue padding lines to approach four times original sample line count
// PAD 062 continue padding lines to approach four times original sample line count
// PAD 063 continue padding lines to approach four times original sample line count
// PAD 064 continue padding lines to approach four times original sample line count
// PAD 065 continue padding lines to approach four times original sample line count
// PAD 066 continue padding lines to approach four times original sample line count
// PAD 067 continue padding lines to approach four times original sample line count
// PAD 068 continue padding lines to approach four times original sample line count
// PAD 069 continue padding lines to approach four times original sample line count
// PAD 070 continue padding lines to approach four times original sample line count
// PAD 071 continue padding lines to approach four times original sample line count
// PAD 072 continue padding lines to approach four times original sample line count
// PAD 073 continue padding lines to approach four times original sample line count
// PAD 074 continue padding lines to approach four times original sample line count
// PAD 075 continue padding lines to approach four times original sample line count
// PAD 076 continue padding lines to approach four times original sample line count
// PAD 077 continue padding lines to approach four times original sample line count
// PAD 078 continue padding lines to approach four times original sample line count
// PAD 079 continue padding lines to approach four times original sample line count
// PAD 080 continue padding lines to approach four times original sample line count
// PAD 081 continue padding lines to approach four times original sample line count
// PAD 082 continue padding lines to approach four times original sample line count
// PAD 083 continue padding lines to approach four times original sample line count
// PAD 084 continue padding lines to approach four times original sample line count
// PAD 085 continue padding lines to approach four times original sample line count
// PAD 086 continue padding lines to approach four times original sample line count
// PAD 087 continue padding lines to approach four times original sample line count
// PAD 088 continue padding lines to approach four times original sample line count
// PAD 089 continue padding lines to approach four times original sample line count
// PAD 090 continue padding lines to approach four times original sample line count
// PAD 091 continue padding lines to approach four times original sample line count
// PAD 092 continue padding lines to approach four times original sample line count
// PAD 093 continue padding lines to approach four times original sample line count
// PAD 094 continue padding lines to approach four times original sample line count
// PAD 095 continue padding lines to approach four times original sample line count
// PAD 096 continue padding lines to approach four times original sample line count
// PAD 097 continue padding lines to approach four times original sample line count
// PAD 098 continue padding lines to approach four times original sample line count
// PAD 099 continue padding lines to approach four times original sample line count
// PAD 100 continue padding lines to approach four times original sample line count
// PAD 101 continue padding lines to approach four times original sample line count
// PAD 102 continue padding lines to approach four times original sample line count
// PAD 103 continue padding lines to approach four times original sample line count
// PAD 104 continue padding lines to approach four times original sample line count
// PAD 105 continue padding lines to approach four times original sample line count
// PAD 106 continue padding lines to approach four times original sample line count
// PAD 107 continue padding lines to approach four times original sample line count
// PAD 108 continue padding lines to approach four times original sample line count
// PAD 109 continue padding lines to approach four times original sample line count
// PAD 110 continue padding lines to approach four times original sample line count
// PAD 111 continue padding lines to approach four times original sample line count
// PAD 112 continue padding lines to approach four times original sample line count
// PAD 113 continue padding lines to approach four times original sample line count
// PAD 114 continue padding lines to approach four times original sample line count
// PAD 115 continue padding lines to approach four times original sample line count
// PAD 116 continue padding lines to approach four times original sample line count
// PAD 117 continue padding lines to approach four times original sample line count
// PAD 118 continue padding lines to approach four times original sample line count
// PAD 119 continue padding lines to approach four times original sample line count
// PAD 120 continue padding lines to approach four times original sample line count
// PAD 121 continue padding lines to approach four times original sample line count
// PAD 122 continue padding lines to approach four times original sample line count
// PAD 123 continue padding lines to approach four times original sample line count
// PAD 124 continue padding lines to approach four times original sample line count
// PAD 125 continue padding lines to approach four times original sample line count
// PAD 126 continue padding lines to approach four times original sample line count
// PAD 127 continue padding lines to approach four times original sample line count
// PAD 128 continue padding lines to approach four times original sample line count
// PAD 129 continue padding lines to approach four times original sample line count
// PAD 130 continue padding lines to approach four times original sample line count
// PAD 131 continue padding lines to approach four times original sample line count
// PAD 132 continue padding lines to approach four times original sample line count
// PAD 133 continue padding lines to approach four times original sample line count
// PAD 134 continue padding lines to approach four times original sample line count
// PAD 135 continue padding lines to approach four times original sample line count
// PAD 136 continue padding lines to approach four times original sample line count
// PAD 137 continue padding lines to approach four times original sample line count
// PAD 138 continue padding lines to approach four times original sample line count
// PAD 139 continue padding lines to approach four times original sample line count
// PAD 140 continue padding lines to approach four times original sample line count
// PAD 141 continue padding lines to approach four times original sample line count
// PAD 142 continue padding lines to approach four times original sample line count
// PAD 143 continue padding lines to approach four times original sample line count
// PAD 144 continue padding lines to approach four times original sample line count
// PAD 145 continue padding lines to approach four times original sample line count
// PAD 146 continue padding lines to approach four times original sample line count
// PAD 147 continue padding lines to approach four times original sample line count
// PAD 148 continue padding lines to approach four times original sample line count
// PAD 149 continue padding lines to approach four times original sample line count
// PAD 150 continue padding lines to approach four times original sample line count
// PAD 151 continue padding lines to approach four times original sample line count
// PAD 152 continue padding lines to approach four times original sample line count
// PAD 153 continue padding lines to approach four times original sample line count
// PAD 154 continue padding lines to approach four times original sample line count
// PAD 155 continue padding lines to approach four times original sample line count
// PAD 156 continue padding lines to approach four times original sample line count
// PAD 157 continue padding lines to approach four times original sample line count
// PAD 158 continue padding lines to approach four times original sample line count
// PAD 159 continue padding lines to approach four times original sample line count
// PAD 160 continue padding lines to approach four times original sample line count
// PAD 161 continue padding lines to approach four times original sample line count
// PAD 162 continue padding lines to approach four times original sample line count
// PAD 163 continue padding lines to approach four times original sample line count
// PAD 164 continue padding lines to approach four times original sample line count
// PAD 165 continue padding lines to approach four times original sample line count
// PAD 166 continue padding lines to approach four times original sample line count
// PAD 167 continue padding lines to approach four times original sample line count
// PAD 168 continue padding lines to approach four times original sample line count
// PAD 169 continue padding lines to approach four times original sample line count
// PAD 170 continue padding lines to approach four times original sample line count
// PAD 171 continue padding lines to approach four times original sample line count
// PAD 172 continue padding lines to approach four times original sample line count
// PAD 173 continue padding lines to approach four times original sample line count
// PAD 174 continue padding lines to approach four times original sample line count
// PAD 175 continue padding lines to approach four times original sample line count
// PAD 176 continue padding lines to approach four times original sample line count
// PAD 177 continue padding lines to approach four times original sample line count
// PAD 178 continue padding lines to approach four times original sample line count
// PAD 179 continue padding lines to approach four times original sample line count
// PAD 180 continue padding lines to approach four times original sample line count
// PAD 181 continue padding lines to approach four times original sample line count
// PAD 182 continue padding lines to approach four times original sample line count
// PAD 183 continue padding lines to approach four times original sample line count
// PAD 184 continue padding lines to approach four times original sample line count
// PAD 185 continue padding lines to approach four times original sample line count
// PAD 186 continue padding lines to approach four times original sample line count
// PAD 187 continue padding lines to approach four times original sample line count
// PAD 188 continue padding lines to approach four times original sample line count
// PAD 189 continue padding lines to approach four times original sample line count
// PAD 190 continue padding lines to approach four times original sample line count
// PAD 191 continue padding lines to approach four times original sample line count
// PAD 192 continue padding lines to approach four times original sample line count
// PAD 193 continue padding lines to approach four times original sample line count
// PAD 194 continue padding lines to approach four times original sample line count
// PAD 195 continue padding lines to approach four times original sample line count
// PAD 196 continue padding lines to approach four times original sample line count
// PAD 197 continue padding lines to approach four times original sample line count
// PAD 198 continue padding lines to approach four times original sample line count
// PAD 199 continue padding lines to approach four times original sample line count
// PAD 200 continue padding lines to approach four times original sample line count
// PAD 201 continue padding lines to approach four times original sample line count
// PAD 202 continue padding lines to approach four times original sample line count
// PAD 203 continue padding lines to approach four times original sample line count
// PAD 204 continue padding lines to approach four times original sample line count
// PAD 205 continue padding lines to approach four times original sample line count
// PAD 206 continue padding lines to approach four times original sample line count
// PAD 207 continue padding lines to approach four times original sample line count
// PAD 208 continue padding lines to approach four times original sample line count
// PAD 209 continue padding lines to approach four times original sample line count
// PAD 210 continue padding lines to approach four times original sample line count
// PAD 211 continue padding lines to approach four times original sample line count
// PAD 212 continue padding lines to approach four times original sample line count
// PAD 213 continue padding lines to approach four times original sample line count
// PAD 214 continue padding lines to approach four times original sample line count
// PAD 215 continue padding lines to approach four times original sample line count
// PAD 216 continue padding lines to approach four times original sample line count
// PAD 217 continue padding lines to approach four times original sample line count
// PAD 218 continue padding lines to approach four times original sample line count
// PAD 219 continue padding lines to approach four times original sample line count
// PAD 220 continue padding lines to approach four times original sample line count
// PAD 221 continue padding lines to approach four times original sample line count
// PAD 222 continue padding lines to approach four times original sample line count
// PAD 223 continue padding lines to approach four times original sample line count
// PAD 224 continue padding lines to approach four times original sample line count
// PAD 225 continue padding lines to approach four times original sample line count
// PAD 226 continue padding lines to approach four times original sample line count
// PAD 227 continue padding lines to approach four times original sample line count
// PAD 228 continue padding lines to approach four times original sample line count
// PAD 229 continue padding lines to approach four times original sample line count
// PAD 230 continue padding lines to approach four times original sample line count
// PAD 231 continue padding lines to approach four times original sample line count
// PAD 232 continue padding lines to approach four times original sample line count
// PAD 233 continue padding lines to approach four times original sample line count
// PAD 234 continue padding lines to approach four times original sample line count
// PAD 235 continue padding lines to approach four times original sample line count
// PAD 236 continue padding lines to approach four times original sample line count
// PAD 237 continue padding lines to approach four times original sample line count
// PAD 238 continue padding lines to approach four times original sample line count
// PAD 239 continue padding lines to approach four times original sample line count
// PAD 240 continue padding lines to approach four times original sample line count
// PAD 241 continue padding lines to approach four times original sample line count
// PAD 242 continue padding lines to approach four times original sample line count
// PAD 243 continue padding lines to approach four times original sample line count
// PAD 244 continue padding lines to approach four times original sample line count
// PAD 245 continue padding lines to approach four times original sample line count
// PAD 246 continue padding lines to approach four times original sample line count
// PAD 247 continue padding lines to approach four times original sample line count
// PAD 248 continue padding lines to approach four times original sample line count
// PAD 249 continue padding lines to approach four times original sample line count
// PAD 250 continue padding lines to approach four times original sample line count
// PAD 251 continue padding lines to approach four times original sample line count
// PAD 252 continue padding lines to approach four times original sample line count
// PAD 253 continue padding lines to approach four times original sample line count
// PAD 254 continue padding lines to approach four times original sample line count
// PAD 255 continue padding lines to approach four times original sample line count
// PAD 256 continue padding lines to approach four times original sample line count
// PAD 257 continue padding lines to approach four times original sample line count
// PAD 258 continue padding lines to approach four times original sample line count
// PAD 259 continue padding lines to approach four times original sample line count
// PAD 260 continue padding lines to approach four times original sample line count
// PAD 261 continue padding lines to approach four times original sample line count
// PAD 262 continue padding lines to approach four times original sample line count
// PAD 263 continue padding lines to approach four times original sample line count
// PAD 264 continue padding lines to approach four times original sample line count

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
    std::cout << "sample2 시작 (길이 확장, 오류 1~12 유지)" << std::endl;
    std::cout << "모든 오류 트리거 실행 시작..." << std::endl;
    trigger_all_20_errors();
    std::cout << "실행 종료." << std::endl;
    return 0;
}
