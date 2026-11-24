#include <iostream>
#include <cstring>
#include <new>

// sample3: sample2(~355줄)의 약 2배 길이.
// 오류 1~12는 별도 함수로 파일 전체에 골고루 배치.
// 사이 간격은 주석 패딩만 사용(가짜 포인터/할당 filler 없음).
// PAD 001 section01 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 002 section01 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 003 section01 cash unit jam vault reject-bin approve decline reverse archive
// PAD 004 section01 log rotate compress upload diagnose calibrate firmware query
// PAD 005 section01 operator path key-echo disabled linedata append flush close
// PAD 006 section01 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 007 section01 terminal risk tap poll success fail retry screens digest verify
// PAD 008 section01 power-fail recover service ticket local deny list nearfull flag
// PAD 009 section01 sample3 goal: twelve bugs scattered evenly across long source
// PAD 010 section01 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 011 section01 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 012 section01 measure finding recall when bugs are spatially distributed
// PAD 013 section01 ATM cassette status host settle pinpad session receipt cut journal
// PAD 014 section01 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 015 section01 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 016 section01 cash unit jam vault reject-bin approve decline reverse archive
// PAD 017 section01 log rotate compress upload diagnose calibrate firmware query
// PAD 018 section01 operator path key-echo disabled linedata append flush close
// PAD 019 section01 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 020 section01 terminal risk tap poll success fail retry screens digest verify
// PAD 021 section01 power-fail recover service ticket local deny list nearfull flag
// PAD 022 section01 sample3 goal: twelve bugs scattered evenly across long source
// PAD 023 section01 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 024 section01 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 025 section01 measure finding recall when bugs are spatially distributed
// PAD 026 section01 ATM cassette status host settle pinpad session receipt cut journal
// PAD 027 section01 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 028 section01 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 029 section01 cash unit jam vault reject-bin approve decline reverse archive
// PAD 030 section01 log rotate compress upload diagnose calibrate firmware query
// PAD 031 section01 operator path key-echo disabled linedata append flush close
// PAD 032 section01 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 033 section01 terminal risk tap poll success fail retry screens digest verify
// PAD 034 section01 power-fail recover service ticket local deny list nearfull flag
// PAD 035 section01 sample3 goal: twelve bugs scattered evenly across long source
// PAD 036 section01 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 037 section01 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 038 section01 measure finding recall when bugs are spatially distributed
// PAD 039 section01 ATM cassette status host settle pinpad session receipt cut journal
// PAD 040 section01 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 041 section01 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 042 section01 cash unit jam vault reject-bin approve decline reverse archive
// PAD 043 section01 log rotate compress upload diagnose calibrate firmware query
// PAD 044 section01 operator path key-echo disabled linedata append flush close
// PAD 045 section01 advice reverse settlement file rotate reconnect backoff heartbeat

void bug_01_uninit_local() {
    // 1. 미초기화 지역 변수 사용 (쓰레기 값 읽기)
    // 앵커: 소거 방지용 포인터 선언(의도 버그 아님)
    int* keep_chunk = nullptr;
    (void)keep_chunk;
    int uninit_local;
    volatile int val1 = uninit_local + 1;
}

// PAD 046 section02 terminal risk tap poll success fail retry screens digest verify
// PAD 047 section02 power-fail recover service ticket local deny list nearfull flag
// PAD 048 section02 sample3 goal: twelve bugs scattered evenly across long source
// PAD 049 section02 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 050 section02 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 051 section02 measure finding recall when bugs are spatially distributed
// PAD 052 section02 ATM cassette status host settle pinpad session receipt cut journal
// PAD 053 section02 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 054 section02 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 055 section02 cash unit jam vault reject-bin approve decline reverse archive
// PAD 056 section02 log rotate compress upload diagnose calibrate firmware query
// PAD 057 section02 operator path key-echo disabled linedata append flush close
// PAD 058 section02 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 059 section02 terminal risk tap poll success fail retry screens digest verify
// PAD 060 section02 power-fail recover service ticket local deny list nearfull flag
// PAD 061 section02 sample3 goal: twelve bugs scattered evenly across long source
// PAD 062 section02 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 063 section02 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 064 section02 measure finding recall when bugs are spatially distributed
// PAD 065 section02 ATM cassette status host settle pinpad session receipt cut journal
// PAD 066 section02 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 067 section02 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 068 section02 cash unit jam vault reject-bin approve decline reverse archive
// PAD 069 section02 log rotate compress upload diagnose calibrate firmware query
// PAD 070 section02 operator path key-echo disabled linedata append flush close
// PAD 071 section02 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 072 section02 terminal risk tap poll success fail retry screens digest verify
// PAD 073 section02 power-fail recover service ticket local deny list nearfull flag
// PAD 074 section02 sample3 goal: twelve bugs scattered evenly across long source
// PAD 075 section02 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 076 section02 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 077 section02 measure finding recall when bugs are spatially distributed
// PAD 078 section02 ATM cassette status host settle pinpad session receipt cut journal
// PAD 079 section02 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 080 section02 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 081 section02 cash unit jam vault reject-bin approve decline reverse archive
// PAD 082 section02 log rotate compress upload diagnose calibrate firmware query
// PAD 083 section02 operator path key-echo disabled linedata append flush close
// PAD 084 section02 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 085 section02 terminal risk tap poll success fail retry screens digest verify
// PAD 086 section02 power-fail recover service ticket local deny list nearfull flag
// PAD 087 section02 sample3 goal: twelve bugs scattered evenly across long source
// PAD 088 section02 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 089 section02 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 090 section02 measure finding recall when bugs are spatially distributed

void bug_02_wild_pointer() {
    // 2. 와일드 포인터(미초기화 포인터) 역참조
    int* wild_ptr;
    volatile int val2 = *wild_ptr;
}

// PAD 091 section03 ATM cassette status host settle pinpad session receipt cut journal
// PAD 092 section03 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 093 section03 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 094 section03 cash unit jam vault reject-bin approve decline reverse archive
// PAD 095 section03 log rotate compress upload diagnose calibrate firmware query
// PAD 096 section03 operator path key-echo disabled linedata append flush close
// PAD 097 section03 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 098 section03 terminal risk tap poll success fail retry screens digest verify
// PAD 099 section03 power-fail recover service ticket local deny list nearfull flag
// PAD 100 section03 sample3 goal: twelve bugs scattered evenly across long source
// PAD 101 section03 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 102 section03 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 103 section03 measure finding recall when bugs are spatially distributed
// PAD 104 section03 ATM cassette status host settle pinpad session receipt cut journal
// PAD 105 section03 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 106 section03 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 107 section03 cash unit jam vault reject-bin approve decline reverse archive
// PAD 108 section03 log rotate compress upload diagnose calibrate firmware query
// PAD 109 section03 operator path key-echo disabled linedata append flush close
// PAD 110 section03 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 111 section03 terminal risk tap poll success fail retry screens digest verify
// PAD 112 section03 power-fail recover service ticket local deny list nearfull flag
// PAD 113 section03 sample3 goal: twelve bugs scattered evenly across long source
// PAD 114 section03 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 115 section03 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 116 section03 measure finding recall when bugs are spatially distributed
// PAD 117 section03 ATM cassette status host settle pinpad session receipt cut journal
// PAD 118 section03 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 119 section03 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 120 section03 cash unit jam vault reject-bin approve decline reverse archive
// PAD 121 section03 log rotate compress upload diagnose calibrate firmware query
// PAD 122 section03 operator path key-echo disabled linedata append flush close
// PAD 123 section03 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 124 section03 terminal risk tap poll success fail retry screens digest verify
// PAD 125 section03 power-fail recover service ticket local deny list nearfull flag
// PAD 126 section03 sample3 goal: twelve bugs scattered evenly across long source
// PAD 127 section03 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 128 section03 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 129 section03 measure finding recall when bugs are spatially distributed
// PAD 130 section03 ATM cassette status host settle pinpad session receipt cut journal
// PAD 131 section03 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 132 section03 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 133 section03 cash unit jam vault reject-bin approve decline reverse archive
// PAD 134 section03 log rotate compress upload diagnose calibrate firmware query
// PAD 135 section03 operator path key-echo disabled linedata append flush close

void bug_03_sprintf_overflow() {
    // 3. sprintf 버퍼 오버플로우
    char ssTemp[10];
    sprintf(ssTemp, "dfsljsdlkfjsldkfdlfksldkfsjlfd");
}

// PAD 136 section04 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 137 section04 terminal risk tap poll success fail retry screens digest verify
// PAD 138 section04 power-fail recover service ticket local deny list nearfull flag
// PAD 139 section04 sample3 goal: twelve bugs scattered evenly across long source
// PAD 140 section04 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 141 section04 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 142 section04 measure finding recall when bugs are spatially distributed
// PAD 143 section04 ATM cassette status host settle pinpad session receipt cut journal
// PAD 144 section04 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 145 section04 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 146 section04 cash unit jam vault reject-bin approve decline reverse archive
// PAD 147 section04 log rotate compress upload diagnose calibrate firmware query
// PAD 148 section04 operator path key-echo disabled linedata append flush close
// PAD 149 section04 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 150 section04 terminal risk tap poll success fail retry screens digest verify
// PAD 151 section04 power-fail recover service ticket local deny list nearfull flag
// PAD 152 section04 sample3 goal: twelve bugs scattered evenly across long source
// PAD 153 section04 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 154 section04 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 155 section04 measure finding recall when bugs are spatially distributed
// PAD 156 section04 ATM cassette status host settle pinpad session receipt cut journal
// PAD 157 section04 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 158 section04 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 159 section04 cash unit jam vault reject-bin approve decline reverse archive
// PAD 160 section04 log rotate compress upload diagnose calibrate firmware query
// PAD 161 section04 operator path key-echo disabled linedata append flush close
// PAD 162 section04 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 163 section04 terminal risk tap poll success fail retry screens digest verify
// PAD 164 section04 power-fail recover service ticket local deny list nearfull flag
// PAD 165 section04 sample3 goal: twelve bugs scattered evenly across long source
// PAD 166 section04 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 167 section04 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 168 section04 measure finding recall when bugs are spatially distributed
// PAD 169 section04 ATM cassette status host settle pinpad session receipt cut journal
// PAD 170 section04 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 171 section04 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 172 section04 cash unit jam vault reject-bin approve decline reverse archive
// PAD 173 section04 log rotate compress upload diagnose calibrate firmware query
// PAD 174 section04 operator path key-echo disabled linedata append flush close
// PAD 175 section04 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 176 section04 terminal risk tap poll success fail retry screens digest verify
// PAD 177 section04 power-fail recover service ticket local deny list nearfull flag
// PAD 178 section04 sample3 goal: twelve bugs scattered evenly across long source
// PAD 179 section04 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 180 section04 padding stays comment-only so prune keeps only intentional bug funcs

void bug_04_memcpy_overflow() {
    // 4. memcpy 크기 초과
    char ssTemp[10];
    memcpy(ssTemp, "dlfkjsdklfjdslfksdjl", 11);
}

// PAD 181 section05 measure finding recall when bugs are spatially distributed
// PAD 182 section05 ATM cassette status host settle pinpad session receipt cut journal
// PAD 183 section05 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 184 section05 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 185 section05 cash unit jam vault reject-bin approve decline reverse archive
// PAD 186 section05 log rotate compress upload diagnose calibrate firmware query
// PAD 187 section05 operator path key-echo disabled linedata append flush close
// PAD 188 section05 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 189 section05 terminal risk tap poll success fail retry screens digest verify
// PAD 190 section05 power-fail recover service ticket local deny list nearfull flag
// PAD 191 section05 sample3 goal: twelve bugs scattered evenly across long source
// PAD 192 section05 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 193 section05 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 194 section05 measure finding recall when bugs are spatially distributed
// PAD 195 section05 ATM cassette status host settle pinpad session receipt cut journal
// PAD 196 section05 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 197 section05 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 198 section05 cash unit jam vault reject-bin approve decline reverse archive
// PAD 199 section05 log rotate compress upload diagnose calibrate firmware query
// PAD 200 section05 operator path key-echo disabled linedata append flush close
// PAD 201 section05 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 202 section05 terminal risk tap poll success fail retry screens digest verify
// PAD 203 section05 power-fail recover service ticket local deny list nearfull flag
// PAD 204 section05 sample3 goal: twelve bugs scattered evenly across long source
// PAD 205 section05 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 206 section05 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 207 section05 measure finding recall when bugs are spatially distributed
// PAD 208 section05 ATM cassette status host settle pinpad session receipt cut journal
// PAD 209 section05 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 210 section05 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 211 section05 cash unit jam vault reject-bin approve decline reverse archive
// PAD 212 section05 log rotate compress upload diagnose calibrate firmware query
// PAD 213 section05 operator path key-echo disabled linedata append flush close
// PAD 214 section05 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 215 section05 terminal risk tap poll success fail retry screens digest verify
// PAD 216 section05 power-fail recover service ticket local deny list nearfull flag
// PAD 217 section05 sample3 goal: twelve bugs scattered evenly across long source
// PAD 218 section05 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 219 section05 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 220 section05 measure finding recall when bugs are spatially distributed
// PAD 221 section05 ATM cassette status host settle pinpad session receipt cut journal
// PAD 222 section05 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 223 section05 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 224 section05 cash unit jam vault reject-bin approve decline reverse archive
// PAD 225 section05 log rotate compress upload diagnose calibrate firmware query

void bug_05_strcat_overflow() {
    // 5. strcat 버퍼 오버플로우
    char ssTemp[10];
    sprintf(ssTemp, "123456789");
    strcat(ssTemp, "1234");
}

// PAD 226 section06 operator path key-echo disabled linedata append flush close
// PAD 227 section06 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 228 section06 terminal risk tap poll success fail retry screens digest verify
// PAD 229 section06 power-fail recover service ticket local deny list nearfull flag
// PAD 230 section06 sample3 goal: twelve bugs scattered evenly across long source
// PAD 231 section06 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 232 section06 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 233 section06 measure finding recall when bugs are spatially distributed
// PAD 234 section06 ATM cassette status host settle pinpad session receipt cut journal
// PAD 235 section06 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 236 section06 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 237 section06 cash unit jam vault reject-bin approve decline reverse archive
// PAD 238 section06 log rotate compress upload diagnose calibrate firmware query
// PAD 239 section06 operator path key-echo disabled linedata append flush close
// PAD 240 section06 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 241 section06 terminal risk tap poll success fail retry screens digest verify
// PAD 242 section06 power-fail recover service ticket local deny list nearfull flag
// PAD 243 section06 sample3 goal: twelve bugs scattered evenly across long source
// PAD 244 section06 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 245 section06 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 246 section06 measure finding recall when bugs are spatially distributed
// PAD 247 section06 ATM cassette status host settle pinpad session receipt cut journal
// PAD 248 section06 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 249 section06 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 250 section06 cash unit jam vault reject-bin approve decline reverse archive
// PAD 251 section06 log rotate compress upload diagnose calibrate firmware query
// PAD 252 section06 operator path key-echo disabled linedata append flush close
// PAD 253 section06 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 254 section06 terminal risk tap poll success fail retry screens digest verify
// PAD 255 section06 power-fail recover service ticket local deny list nearfull flag
// PAD 256 section06 sample3 goal: twelve bugs scattered evenly across long source
// PAD 257 section06 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 258 section06 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 259 section06 measure finding recall when bugs are spatially distributed
// PAD 260 section06 ATM cassette status host settle pinpad session receipt cut journal
// PAD 261 section06 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 262 section06 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 263 section06 cash unit jam vault reject-bin approve decline reverse archive
// PAD 264 section06 log rotate compress upload diagnose calibrate firmware query
// PAD 265 section06 operator path key-echo disabled linedata append flush close
// PAD 266 section06 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 267 section06 terminal risk tap poll success fail retry screens digest verify
// PAD 268 section06 power-fail recover service ticket local deny list nearfull flag
// PAD 269 section06 sample3 goal: twelve bugs scattered evenly across long source
// PAD 270 section06 do not concentrate bugs in one trigger; exercise multi-chunk review

void bug_06_partial_init_array() {
    // 6. 동적 할당 후 부분 초기화된 배열의 미정의 요소 읽기
    int* dyn_arr = new int[10];
    dyn_arr[0] = 1;
    volatile int val5 = dyn_arr[5];
    delete[] dyn_arr;
}

// PAD 271 section07 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 272 section07 measure finding recall when bugs are spatially distributed
// PAD 273 section07 ATM cassette status host settle pinpad session receipt cut journal
// PAD 274 section07 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 275 section07 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 276 section07 cash unit jam vault reject-bin approve decline reverse archive
// PAD 277 section07 log rotate compress upload diagnose calibrate firmware query
// PAD 278 section07 operator path key-echo disabled linedata append flush close
// PAD 279 section07 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 280 section07 terminal risk tap poll success fail retry screens digest verify
// PAD 281 section07 power-fail recover service ticket local deny list nearfull flag
// PAD 282 section07 sample3 goal: twelve bugs scattered evenly across long source
// PAD 283 section07 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 284 section07 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 285 section07 measure finding recall when bugs are spatially distributed
// PAD 286 section07 ATM cassette status host settle pinpad session receipt cut journal
// PAD 287 section07 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 288 section07 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 289 section07 cash unit jam vault reject-bin approve decline reverse archive
// PAD 290 section07 log rotate compress upload diagnose calibrate firmware query
// PAD 291 section07 operator path key-echo disabled linedata append flush close
// PAD 292 section07 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 293 section07 terminal risk tap poll success fail retry screens digest verify
// PAD 294 section07 power-fail recover service ticket local deny list nearfull flag
// PAD 295 section07 sample3 goal: twelve bugs scattered evenly across long source
// PAD 296 section07 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 297 section07 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 298 section07 measure finding recall when bugs are spatially distributed
// PAD 299 section07 ATM cassette status host settle pinpad session receipt cut journal
// PAD 300 section07 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 301 section07 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 302 section07 cash unit jam vault reject-bin approve decline reverse archive
// PAD 303 section07 log rotate compress upload diagnose calibrate firmware query
// PAD 304 section07 operator path key-echo disabled linedata append flush close
// PAD 305 section07 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 306 section07 terminal risk tap poll success fail retry screens digest verify
// PAD 307 section07 power-fail recover service ticket local deny list nearfull flag
// PAD 308 section07 sample3 goal: twelve bugs scattered evenly across long source
// PAD 309 section07 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 310 section07 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 311 section07 measure finding recall when bugs are spatially distributed
// PAD 312 section07 ATM cassette status host settle pinpad session receipt cut journal
// PAD 313 section07 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 314 section07 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 315 section07 cash unit jam vault reject-bin approve decline reverse archive

void bug_07_conditional_uninit() {
    // 7. 조건부 초기화 누락 변수 사용
    int* keep_chunk = nullptr;
    (void)keep_chunk;
    int cond_var;
    bool flag = false;
    if (flag) {
        cond_var = 100;
    }
    volatile int val7 = cond_var;
}

// PAD 316 section08 log rotate compress upload diagnose calibrate firmware query
// PAD 317 section08 operator path key-echo disabled linedata append flush close
// PAD 318 section08 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 319 section08 terminal risk tap poll success fail retry screens digest verify
// PAD 320 section08 power-fail recover service ticket local deny list nearfull flag
// PAD 321 section08 sample3 goal: twelve bugs scattered evenly across long source
// PAD 322 section08 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 323 section08 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 324 section08 measure finding recall when bugs are spatially distributed
// PAD 325 section08 ATM cassette status host settle pinpad session receipt cut journal
// PAD 326 section08 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 327 section08 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 328 section08 cash unit jam vault reject-bin approve decline reverse archive
// PAD 329 section08 log rotate compress upload diagnose calibrate firmware query
// PAD 330 section08 operator path key-echo disabled linedata append flush close
// PAD 331 section08 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 332 section08 terminal risk tap poll success fail retry screens digest verify
// PAD 333 section08 power-fail recover service ticket local deny list nearfull flag
// PAD 334 section08 sample3 goal: twelve bugs scattered evenly across long source
// PAD 335 section08 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 336 section08 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 337 section08 measure finding recall when bugs are spatially distributed
// PAD 338 section08 ATM cassette status host settle pinpad session receipt cut journal
// PAD 339 section08 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 340 section08 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 341 section08 cash unit jam vault reject-bin approve decline reverse archive
// PAD 342 section08 log rotate compress upload diagnose calibrate firmware query
// PAD 343 section08 operator path key-echo disabled linedata append flush close
// PAD 344 section08 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 345 section08 terminal risk tap poll success fail retry screens digest verify
// PAD 346 section08 power-fail recover service ticket local deny list nearfull flag
// PAD 347 section08 sample3 goal: twelve bugs scattered evenly across long source
// PAD 348 section08 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 349 section08 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 350 section08 measure finding recall when bugs are spatially distributed
// PAD 351 section08 ATM cassette status host settle pinpad session receipt cut journal
// PAD 352 section08 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 353 section08 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 354 section08 cash unit jam vault reject-bin approve decline reverse archive
// PAD 355 section08 log rotate compress upload diagnose calibrate firmware query
// PAD 356 section08 operator path key-echo disabled linedata append flush close
// PAD 357 section08 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 358 section08 terminal risk tap poll success fail retry screens digest verify
// PAD 359 section08 power-fail recover service ticket local deny list nearfull flag
// PAD 360 section08 sample3 goal: twelve bugs scattered evenly across long source

void bug_08_uninit_bool() {
    // 8. 미초기화 불리언 플래그 제어 흐름 사용
    int* keep_chunk = nullptr;
    (void)keep_chunk;
    bool uninit_flag;
    volatile int val9 = uninit_flag ? 1 : 0;
}

// PAD 361 section09 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 362 section09 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 363 section09 measure finding recall when bugs are spatially distributed
// PAD 364 section09 ATM cassette status host settle pinpad session receipt cut journal
// PAD 365 section09 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 366 section09 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 367 section09 cash unit jam vault reject-bin approve decline reverse archive
// PAD 368 section09 log rotate compress upload diagnose calibrate firmware query
// PAD 369 section09 operator path key-echo disabled linedata append flush close
// PAD 370 section09 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 371 section09 terminal risk tap poll success fail retry screens digest verify
// PAD 372 section09 power-fail recover service ticket local deny list nearfull flag
// PAD 373 section09 sample3 goal: twelve bugs scattered evenly across long source
// PAD 374 section09 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 375 section09 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 376 section09 measure finding recall when bugs are spatially distributed
// PAD 377 section09 ATM cassette status host settle pinpad session receipt cut journal
// PAD 378 section09 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 379 section09 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 380 section09 cash unit jam vault reject-bin approve decline reverse archive
// PAD 381 section09 log rotate compress upload diagnose calibrate firmware query
// PAD 382 section09 operator path key-echo disabled linedata append flush close
// PAD 383 section09 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 384 section09 terminal risk tap poll success fail retry screens digest verify
// PAD 385 section09 power-fail recover service ticket local deny list nearfull flag
// PAD 386 section09 sample3 goal: twelve bugs scattered evenly across long source
// PAD 387 section09 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 388 section09 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 389 section09 measure finding recall when bugs are spatially distributed
// PAD 390 section09 ATM cassette status host settle pinpad session receipt cut journal
// PAD 391 section09 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 392 section09 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 393 section09 cash unit jam vault reject-bin approve decline reverse archive
// PAD 394 section09 log rotate compress upload diagnose calibrate firmware query
// PAD 395 section09 operator path key-echo disabled linedata append flush close
// PAD 396 section09 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 397 section09 terminal risk tap poll success fail retry screens digest verify
// PAD 398 section09 power-fail recover service ticket local deny list nearfull flag
// PAD 399 section09 sample3 goal: twelve bugs scattered evenly across long source
// PAD 400 section09 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 401 section09 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 402 section09 measure finding recall when bugs are spatially distributed
// PAD 403 section09 ATM cassette status host settle pinpad session receipt cut journal
// PAD 404 section09 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 405 section09 config migrate watchdog dump NVRAM checksum audit privilege deny

void bug_09_memory_leak() {
    // 9. 메모리 누수 (Memory Leak)
    int* leak_ptr = new int(500);
    // delete leak_ptr; 누락됨
    (void)leak_ptr;
}

// PAD 406 section10 cash unit jam vault reject-bin approve decline reverse archive
// PAD 407 section10 log rotate compress upload diagnose calibrate firmware query
// PAD 408 section10 operator path key-echo disabled linedata append flush close
// PAD 409 section10 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 410 section10 terminal risk tap poll success fail retry screens digest verify
// PAD 411 section10 power-fail recover service ticket local deny list nearfull flag
// PAD 412 section10 sample3 goal: twelve bugs scattered evenly across long source
// PAD 413 section10 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 414 section10 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 415 section10 measure finding recall when bugs are spatially distributed
// PAD 416 section10 ATM cassette status host settle pinpad session receipt cut journal
// PAD 417 section10 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 418 section10 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 419 section10 cash unit jam vault reject-bin approve decline reverse archive
// PAD 420 section10 log rotate compress upload diagnose calibrate firmware query
// PAD 421 section10 operator path key-echo disabled linedata append flush close
// PAD 422 section10 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 423 section10 terminal risk tap poll success fail retry screens digest verify
// PAD 424 section10 power-fail recover service ticket local deny list nearfull flag
// PAD 425 section10 sample3 goal: twelve bugs scattered evenly across long source
// PAD 426 section10 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 427 section10 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 428 section10 measure finding recall when bugs are spatially distributed
// PAD 429 section10 ATM cassette status host settle pinpad session receipt cut journal
// PAD 430 section10 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 431 section10 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 432 section10 cash unit jam vault reject-bin approve decline reverse archive
// PAD 433 section10 log rotate compress upload diagnose calibrate firmware query
// PAD 434 section10 operator path key-echo disabled linedata append flush close
// PAD 435 section10 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 436 section10 terminal risk tap poll success fail retry screens digest verify
// PAD 437 section10 power-fail recover service ticket local deny list nearfull flag
// PAD 438 section10 sample3 goal: twelve bugs scattered evenly across long source
// PAD 439 section10 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 440 section10 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 441 section10 measure finding recall when bugs are spatially distributed
// PAD 442 section10 ATM cassette status host settle pinpad session receipt cut journal
// PAD 443 section10 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 444 section10 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 445 section10 cash unit jam vault reject-bin approve decline reverse archive
// PAD 446 section10 log rotate compress upload diagnose calibrate firmware query
// PAD 447 section10 operator path key-echo disabled linedata append flush close
// PAD 448 section10 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 449 section10 terminal risk tap poll success fail retry screens digest verify
// PAD 450 section10 power-fail recover service ticket local deny list nearfull flag

void bug_10_double_free() {
    // 10. 이중 해제 (Double Free)
    int* double_ptr = new int(100);
    delete double_ptr;
    delete double_ptr; // 두 번째 해제
}

// PAD 451 section11 sample3 goal: twelve bugs scattered evenly across long source
// PAD 452 section11 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 453 section11 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 454 section11 measure finding recall when bugs are spatially distributed
// PAD 455 section11 ATM cassette status host settle pinpad session receipt cut journal
// PAD 456 section11 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 457 section11 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 458 section11 cash unit jam vault reject-bin approve decline reverse archive
// PAD 459 section11 log rotate compress upload diagnose calibrate firmware query
// PAD 460 section11 operator path key-echo disabled linedata append flush close
// PAD 461 section11 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 462 section11 terminal risk tap poll success fail retry screens digest verify
// PAD 463 section11 power-fail recover service ticket local deny list nearfull flag
// PAD 464 section11 sample3 goal: twelve bugs scattered evenly across long source
// PAD 465 section11 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 466 section11 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 467 section11 measure finding recall when bugs are spatially distributed
// PAD 468 section11 ATM cassette status host settle pinpad session receipt cut journal
// PAD 469 section11 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 470 section11 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 471 section11 cash unit jam vault reject-bin approve decline reverse archive
// PAD 472 section11 log rotate compress upload diagnose calibrate firmware query
// PAD 473 section11 operator path key-echo disabled linedata append flush close
// PAD 474 section11 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 475 section11 terminal risk tap poll success fail retry screens digest verify
// PAD 476 section11 power-fail recover service ticket local deny list nearfull flag
// PAD 477 section11 sample3 goal: twelve bugs scattered evenly across long source
// PAD 478 section11 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 479 section11 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 480 section11 measure finding recall when bugs are spatially distributed
// PAD 481 section11 ATM cassette status host settle pinpad session receipt cut journal
// PAD 482 section11 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 483 section11 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 484 section11 cash unit jam vault reject-bin approve decline reverse archive
// PAD 485 section11 log rotate compress upload diagnose calibrate firmware query
// PAD 486 section11 operator path key-echo disabled linedata append flush close
// PAD 487 section11 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 488 section11 terminal risk tap poll success fail retry screens digest verify
// PAD 489 section11 power-fail recover service ticket local deny list nearfull flag
// PAD 490 section11 sample3 goal: twelve bugs scattered evenly across long source
// PAD 491 section11 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 492 section11 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 493 section11 measure finding recall when bugs are spatially distributed
// PAD 494 section11 ATM cassette status host settle pinpad session receipt cut journal

void bug_11_heap_overflow() {
    // 11. 힙 버퍼 오버플로우 (Heap Buffer Overflow)
    int* heap_buf = new int[5];
    heap_buf[5] = 999; // 할당된 크기(5)를 넘어선 영역에 쓰기
    delete[] heap_buf;
}

// PAD 495 section12 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 496 section12 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 497 section12 cash unit jam vault reject-bin approve decline reverse archive
// PAD 498 section12 log rotate compress upload diagnose calibrate firmware query
// PAD 499 section12 operator path key-echo disabled linedata append flush close
// PAD 500 section12 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 501 section12 terminal risk tap poll success fail retry screens digest verify
// PAD 502 section12 power-fail recover service ticket local deny list nearfull flag
// PAD 503 section12 sample3 goal: twelve bugs scattered evenly across long source
// PAD 504 section12 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 505 section12 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 506 section12 measure finding recall when bugs are spatially distributed
// PAD 507 section12 ATM cassette status host settle pinpad session receipt cut journal
// PAD 508 section12 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 509 section12 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 510 section12 cash unit jam vault reject-bin approve decline reverse archive
// PAD 511 section12 log rotate compress upload diagnose calibrate firmware query
// PAD 512 section12 operator path key-echo disabled linedata append flush close
// PAD 513 section12 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 514 section12 terminal risk tap poll success fail retry screens digest verify
// PAD 515 section12 power-fail recover service ticket local deny list nearfull flag
// PAD 516 section12 sample3 goal: twelve bugs scattered evenly across long source
// PAD 517 section12 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 518 section12 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 519 section12 measure finding recall when bugs are spatially distributed
// PAD 520 section12 ATM cassette status host settle pinpad session receipt cut journal
// PAD 521 section12 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 522 section12 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 523 section12 cash unit jam vault reject-bin approve decline reverse archive
// PAD 524 section12 log rotate compress upload diagnose calibrate firmware query
// PAD 525 section12 operator path key-echo disabled linedata append flush close
// PAD 526 section12 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 527 section12 terminal risk tap poll success fail retry screens digest verify
// PAD 528 section12 power-fail recover service ticket local deny list nearfull flag
// PAD 529 section12 sample3 goal: twelve bugs scattered evenly across long source
// PAD 530 section12 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 531 section12 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 532 section12 measure finding recall when bugs are spatially distributed
// PAD 533 section12 ATM cassette status host settle pinpad session receipt cut journal
// PAD 534 section12 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 535 section12 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 536 section12 cash unit jam vault reject-bin approve decline reverse archive
// PAD 537 section12 log rotate compress upload diagnose calibrate firmware query
// PAD 538 section12 operator path key-echo disabled linedata append flush close

void bug_12_stack_overflow() {
    // 12. 스택 버퍼 오버플로우 (Stack Buffer Overflow)
    int* keep_chunk = nullptr;
    (void)keep_chunk;
    int stack_buf[3];
    stack_buf[5] = 777; // 스택 경계 초과 쓰기
}

// PAD 539 section13 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 540 section13 terminal risk tap poll success fail retry screens digest verify
// PAD 541 section13 power-fail recover service ticket local deny list nearfull flag
// PAD 542 section13 sample3 goal: twelve bugs scattered evenly across long source
// PAD 543 section13 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 544 section13 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 545 section13 measure finding recall when bugs are spatially distributed
// PAD 546 section13 ATM cassette status host settle pinpad session receipt cut journal
// PAD 547 section13 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 548 section13 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 549 section13 cash unit jam vault reject-bin approve decline reverse archive
// PAD 550 section13 log rotate compress upload diagnose calibrate firmware query
// PAD 551 section13 operator path key-echo disabled linedata append flush close
// PAD 552 section13 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 553 section13 terminal risk tap poll success fail retry screens digest verify
// PAD 554 section13 power-fail recover service ticket local deny list nearfull flag
// PAD 555 section13 sample3 goal: twelve bugs scattered evenly across long source
// PAD 556 section13 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 557 section13 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 558 section13 measure finding recall when bugs are spatially distributed
// PAD 559 section13 ATM cassette status host settle pinpad session receipt cut journal
// PAD 560 section13 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 561 section13 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 562 section13 cash unit jam vault reject-bin approve decline reverse archive
// PAD 563 section13 log rotate compress upload diagnose calibrate firmware query
// PAD 564 section13 operator path key-echo disabled linedata append flush close
// PAD 565 section13 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 566 section13 terminal risk tap poll success fail retry screens digest verify
// PAD 567 section13 power-fail recover service ticket local deny list nearfull flag
// PAD 568 section13 sample3 goal: twelve bugs scattered evenly across long source
// PAD 569 section13 do not concentrate bugs in one trigger; exercise multi-chunk review
// PAD 570 section13 padding stays comment-only so prune keeps only intentional bug funcs
// PAD 571 section13 measure finding recall when bugs are spatially distributed
// PAD 572 section13 ATM cassette status host settle pinpad session receipt cut journal
// PAD 573 section13 network keepalive EMV AID CVM contactless UI idle menu amount
// PAD 574 section13 config migrate watchdog dump NVRAM checksum audit privilege deny
// PAD 575 section13 cash unit jam vault reject-bin approve decline reverse archive
// PAD 576 section13 log rotate compress upload diagnose calibrate firmware query
// PAD 577 section13 operator path key-echo disabled linedata append flush close
// PAD 578 section13 advice reverse settlement file rotate reconnect backoff heartbeat
// PAD 579 section13 terminal risk tap poll success fail retry screens digest verify
// PAD 580 section13 power-fail recover service ticket local deny list nearfull flag
// PAD 581 section13 sample3 goal: twelve bugs scattered evenly across long source
// PAD 582 section13 do not concentrate bugs in one trigger; exercise multi-chunk review

int main() {
    std::cout << "sample3 시작 (길이 확장, 오류 1~12를 파일 전역에 분산)" << std::endl;
    bug_01_uninit_local();
    bug_02_wild_pointer();
    bug_03_sprintf_overflow();
    bug_04_memcpy_overflow();
    bug_05_strcat_overflow();
    bug_06_partial_init_array();
    bug_07_conditional_uninit();
    bug_08_uninit_bool();
    bug_09_memory_leak();
    bug_10_double_free();
    bug_11_heap_overflow();
    bug_12_stack_overflow();
    std::cout << "실행 종료." << std::endl;
    return 0;
}
