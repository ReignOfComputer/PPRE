
// Platinum offsets
#include "../../include/ppre.h"

typedef int (*func_t)(int, int, int, int);

struct script_state {
    unsigned char frame_id;
    // 0x1
    unsigned char ret;
    unsigned char u2, u3;
    // 0x4
    int *command; // used when ret == 2
    // 0x8
    uint8_t *buf_ptr;
    /* Keeps a copy of buf_ptr to be restored when current is exhausted.
     * Next is state->frames[frame_id+1]
     */
    uint8_t *frames[20];
    unsigned char u4[0x50];
    // 0x5c
    int *command_table;
    // 0x60
    int command_count;
    // 0x64
    int vals[0x10]; // unknown length and purpose
    int u74;
    // 0x78
    int u78;
    int u7c; // pad
    // 0x80
    int u5;
};

int script_handler(script_state* r0, int r1, int r2, int r3){
    script_state *r4;

    r4 = r0;
    r1 = r4->ret;
    if(r1 != 0){
        if(r1 == 0){
            return 0;
        }
        if(r1 == 1 || r1 == 2){
            if(r1 == 2){
                // 0x3e796
                r1 = r4->command;
                if(r1 == 0){
                    r4->ret = 1;
                }else{
                    r0 = (*r1)((script_state*)r0); // switch/exec
                    if(r0 != 1){
                        return 1;
                    }
                    r4->ret = 1;
                    return 1;
                }
            }
            while(r4->buf_ptr){
                // 0x3e7ae
                r1 = get_command(r4);
                r0 = r4->command_count;
                if(r1 >= r0){
                    // 0x3e7d2
                    r2 = r4->command_table; // script table offset
                    r1 = r2[r1];
                    r0 = (*r1)(r4); // switch/exec
                    if(r0 == 1){
                        return 1;
                    }
                }else{
                    func_22974(r0);
                    r4->ret = 0;
                    return 0;
                }
            }
            r4->ret = 0;
            return 0;
        }
        return 1;
    }

    return 0;
}


int get_command(script_state *r0) {
    // 0x3e838
    int r1 = r0->buf_ptr;
    int r3 = r1+1;
    r0->buf_ptr = r3;
    unsigned char r2 = ((unsigned char*)r1)[0];
    r1 = r3+1;
    r0->buf_ptr = r1;
    r0 = ((unsigned char*)r3)[0];
    r0 <<= 8;
    r0 += r2;
    return r0 & 0xFFFF;
}

int read16(script_state *r0) {
    // 0x38c30
    int r1 = r0->buf_ptr;
    int r3 = r1+1;
    r0->buf_ptr = r3;
    unsigned char r2 = ((unsigned char*)r1)[0];
    r1 = r3+1;
    r0->buf_ptr = r1;
    r0 = ((unsigned char*)r3)[0];
    r0 <<= 8;
    r0 += r2;
    return r0 & 0xFFFF;
}

int read32(script_state *r0){
    // 0x38c48
    int r1 = r0->buf_ptr;
    int r2 = r1+1;
    r0->buf_ptr = r2;
    unsigned char r3 = ((unsigned char*)r1)[0];
    r1 = r2+1;
    int r5 = r1+1;
    r0->buf_ptr = r1;
    r2 = ((unsigned char*)r2)[0];
    int r4 = r5+1;
    r0->buf_ptr = r5;
    r1 = ((unsigned char*)r1)[0];
    r0->buf_ptr = r4;
    int r0 = ((unsigned char*)r5)[0];
    r4 = 0;
    r0 <<= 8;
    r0 += r1;
    r0 <<= 8;
    r0 += r2;
    r0 <<= 8;
    r0 += r3;
    return r0;
}

// Diamond commands (some for reference)

int cmd_0000(script_state *r0) {
    return 0;
}

int cmd_0001(script_state *r0) {
    return 0;
}

int cmd_0002(script_state *r0) {
    r0->ret = 0;
    r0->buf_ptr = 0;
    return 0;
}

int func_394b8(int r0, int r1){
    int r5 = r0;
    r0 = ((int*)r5)[12];
    int r4 = r1;
    func_462ac(r0, r1);
    r1 = 1<<14;
    if(r4 < r1){
        r1 <<= 1;
        // TODO
    }else{
        return 0;
    }
}

int cmd_0003(script_state *r0) {
    script_state *r5 = r0;
    int r6 = r5->u5;
    int r7 = read16(r5);
    int r4 = read16(r5);
    r0 = func_394b8(r6, r4);
    ((uint16_t *)r0)[0] = r7;
    int r1 = 0x020399e9;
    r5->vals[0] = r4;
    r5->ret = 2;
    r5->command = r1;
    return 1;
}

int func_399e9(script_state *r0) {
    int r1 = r0->vals[0];
    r1 &= 0xFFFF;
    int r0 = r0->u5;
    r0 = func_394b8(r0, r1);
    r1 = r0;
    ((uint16_t *)r0)[0] = r0-1;
    if(r0 != 1){
        return 0;
    }else{
        return 1;
    }
}

int cmd_0004(script_state *r0) {
    int r3 = *((unsigned char*)(r0->buf_ptr++));
    int r2 = *((unsigned char*)(r0->buf_ptr++));
    int r1 = r3 << 2;
    r0->vals[r1] = r2;
    return 0;
}

int func_38bdc(script_state *r0, int r1) {
    unsigned char r3 = r0->frame_id;
    int r2 = r3+1;
    if(r2 < 20){
        r2 = r3 << 2;
        r2 = r0+r2;
        *(r2+12) = r1;
        r1 = r0->frame_id+1;
        r0->frame_id = r1;
        return 0;
    }else{
        return 1;
    }
}

int func_38c10(script_state *r0, int r1) {
    r0->buf_ptr = r1;
    return;
}

int func_38c14(script_state *r0, int r1) {
    script_state* r5 = r0;
    int r4 = r1;
    r1 = r5->buf_ptr;
    r0 = func_38bdc(r0, r1);
    r5->buf_ptr = r4;
    return r0;
}

int cmd_0022(script_state *r0) {
    // 0x39cf9 - Jump
    int r2 = read32(r0);
    uint8_t* r1 = r0->buf_ptr;
    r1 += r2;
    func_38c10(r0, r1);
    return 0;
}


int cmd_0026(script_state *r0) {
    // 0x39dad - Goto
    int r2 = read32(r0);
    uint8_t* r1 = r0->buf_ptr;
    r1 += r2;
    r0 = func_38c14(r0, r1);
    return r0;
}

int func_462e4(int r0, int r1){
    int r4 = r1;
    r0 = func_46338(r0, r1);
    if(r0 == 0){
        return 0;
    }
    int r5 = r4 >> 31;
    int r3 = r4 << 29;
    r3 = r3-r5;
    int r2 = 29;
}

int func_462ac(int r0, int r1){
    func_t r3 = 0x02022611;
    r1 = 4;
    // r0 = r3(r0, 4);
    // 0x02022611
    int r4 = r1;
    int r5 = r0;
    if(r4 < 0x24){
        r0 = 0x85 << 2;
        int r2 = r5+r0;
        r0 = r4 << 4;
        r1 = r5+r0; // r1 = arg0+(arg1 << 4);
        r0 = 0x0002022c;
        r0 = *(r1+r0);
        return r2 + r0;
    }else{
        // 0x20c2c
        r0 = func_31810(r0);
        if(r0 == 0){
            return 0;
        }
        r0 = func_cd374(r0);
        if(r0 == 18){
            return 18;
        }
        return func_8a9b8(r0);
    }
}

int func_3953c(int r0, int r1){
    int r5 = r0;
    r0 = ((int*)r5)[12];
    int r4 = r1;
    r0 = func_462ac(r0, r1);
    r1 = r4;
    r0 = func_462e4(r0, r1);
    return r0;
}

int func_39550(int r0, int r1){
    int r5 = r0;
    r0 = ((int*)r5)[12];
    int r4 = r1;
    r0 = func_462ac(r0, r1);
    r1 = r4;
    r0 = func_4630c(r0, r1);
    return r0;
}

int cmd_0030(script_state *r0){
    // 0x39e39 - Setflag($1)
    int r4 = r0->u5;
    int r1 = read16(r0);
    int r0 = func_3953c(r4, r1);
    return 0;
}

int cmd_0031(script_state *r0){
    // 0x39e50 - Clearflag($1)
    int r4 = r0->u5;
    int r1 = read16(r0);
    int r0 = func_39550(r4, r1);
    return 0;
}

int cmd_0040(script_state *r0){
    // 0x39fb9 - Setvar($1, $2)
    script_state* r4 = r0;
    int r1 = read16(r0);
    int r0 = r0->u5;
    int r5 = func_394b8(r0, r1);
    script_state* r0 = r4;
    int r0 = read16(r0);
    ((uint16_t *)r5)[0] = (uint16_t)r0;
    return 0;
}

int cmd_0041(script_state *r0){
    // 0x39fdd - Copyvar($1, $2)
    script_state* r5 = r0;
    int r1 = read16(r0);
    int r0 = r0->u5;
    int r4 = func_394b8(r0, r1);
    script_state* r0 = r5;
    int r1 = read16(r0);
    int r0 = r0->u5;
    int r0 = func_394b8(r0, r1);
    ((uint16_t *)r4)[0] = ((uint16_t *)r0)[0];
    return 0;
}

int cmd_0042(script_state *r0){
    // 0x3a00d - 002A($1, $2)
    script_state* r4 = r0;
    int r1 = read16(r0);
    int r0 = r4->u5;
    r0 = func_394b8(r0, r1);
    int r5 = func_39550(r4, r1);
    script_state* r0 = r4;
    r1 = read16(r0);
    int r0 = r0->u5;
    r0 = func_394f0(r0, r1);
    ((uint16_t *)r5)[0] = (uint16_t)r0;
    return 0;
}

int cmd_0043(script_state *r0){
    // 0x3a039 - Message2($1)
    int r2 = *((unsigned char*)(r0->buf_ptr++));
    int r1 = r0->u78;
    func_1e2c24(r0, r1);
    return 0;
}

int cmd_0044(script_state *r0){
    // 0x3a2c4 - Message($1)
    int r3 = 1;
    int r2 = *((unsigned char*)(r0->buf_ptr++));
    int r1 = r0->u78;
    func_1e2bd0(r0, r1);
    func_38b5c(r0, 0x203a2f1);
    return 1;
}

int cmd_0541(script_state *r0){
    // 0x41c38
    int a, b, c;

    script_state* r4 = r0;
    int r6 = func_39438(r0->u5, 15);
    int r5 = func_2881c(r0->u5[12]);
    script_state* r0 = r4;
    int r7 = r0->u5[12];
    int r0 = read16(r0);
    switch(r0) {
        case 0:  // 0x41c86
            script_state* r0 = r4;
            int r1 = read16(r0);
            r6 = func_394f0(r0->u5, r1);
            r1 = read16(r0);
            r4 = func_394b8(r0->u5, r1);
            r0 =func_28828(r5, r6);
            *r4 = r0;
            return 0;
        case 1: // 0x41cbc
            // read16() *2
            return 0;
        case 2: // 0x41cf2
            // read16() *2
            return 0;
        case 3: // 0x41d28
            // read16() *2
            return 0;
        case 4: // 0x41d5e
            // read16() *1
            return 0;
        case 5: // 0x41d94
            // read16() *1
            return 0;
        case 6: // 0x41dce
            return 0;
        default:  // > 6
            return 0;
    }
}

int cmd_0574(script_state *r0){
    uint32_t a, b, c, d, e, f, g, h;

    script_state* r4 = r0;
    int r0 = read16(r0);
    switch(r0) {
        case 0:
            // 0x42d4a

            return 0;
        case 1:
            // 0x42d74
            // read16()
            return 0;
        case 2:
            // 0x42da0
            // read16()
            return 0;
        case 3:
            // 0x42dc0
            // read16()
            return 0;
        case 4:
            // 0x42dfc
            // read16()
            return 0;
        case 5:
            // 0x42e2e
            // read16()
            // read16()
            return 0;
        case 6:
            // 0x42e9a
            // read16()
            // read16()
            return 0;
        case 7:
            // 0x42d58

            return 0;
        case 8:
            // 0x42d66

            return 0;
        default:
            return 0;
    }
}

int cmd_0565(script_state *r0){
    script_state* r4 = r0;
    int r0 = read16(r0);
    switch(r0){
        case 0:
            // 0x41e68
            // read16()
            break;
        case 1:
            // 0x41e88
            // read16()
            // read16()
            // read16()
            break;
        case 2:
            // 0x41f24

            break;
        case 3:
            // 0x41eca
            // read16()
            // read16()
            // read16()
            break;
        case 4:
            // 0x41f2e
            // read16()
            // read16()
            break;
        case 5:
            // 0x41f68
            // read16()
            // read16()
            // read16()
            break;
        case 6:
            // 0x41fb4
            // read16()
        default:
            break;
    }
    return 0;
}

int cmd_0649(script_state *r0){
    uint8_t a[8];
    script_state* r5 = r0;
    int r1 = read16(r0);
    int r4 = func_394b8(r0->u5, r1);
    int r2 = 0;
    uint8_t *r3 = a;

    do {
        int r6 = r0->buf_ptr;
        r1 = r5->buf_ptr;
        r6 += 1;
        r0->buf_ptr = r6;
        uint8_t r1 = *((uint8_t *)r1);
        r2 += 1;
        r3[0] = 1;
        r3 += 1;
    } while(r2 < 5);

    int r6 = *((unsigned char*)(r5->buf_ptr++));
    int r0 = func_27e5c(4);
    r1 = a;
    r2 = r6;
    r3 = 0;
    int r7 = r0;
    func_27f04(r0, r1, r2, r3);
    r0 = r5->u5[12];
}

