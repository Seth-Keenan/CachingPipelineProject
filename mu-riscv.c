#include "mu-riscv.h"

/***************************************************************/
/* Print out a list of commands available                                                                  */
/***************************************************************/
void help() {
	printf("------------------------------------------------------------------\n\n");
	printf("\t**********MU-RISCV Help MENU**********\n\n");
	printf("sim\t-- simulate program to completion \n");
	printf("run <n>\t-- simulate program for <n> instructions\n");
	printf("rdump\t-- dump register values\n");
	printf("reset\t-- clears all registers/memory and re-loads the program\n");
	printf("input <reg> <val>\t-- set GPR <reg> to <val>\n");
	printf("mdump <start> <stop>\t-- dump memory from <start> to <stop> address\n");
	printf("high <val>\t-- set the HI register to <val>\n");
	printf("low <val>\t-- set the LO register to <val>\n");
	printf("print\t-- print the program loaded into memory\n");
	printf("show\t-- print the current content of the pipeline registers\n");
	printf("f [0 | 1]\t-- Enable/disable forwarding.\n");
	printf("?\t-- display help menu\n");
	printf("quit\t-- exit the simulator\n\n");
	printf("------------------------------------------------------------------\n\n");
}

/***************************************************************/
/* Read a 32-bit word from memory                                                                            */
/***************************************************************/
uint32_t mem_read_32(uint32_t address)
{
	int i;
	for (i = 0; i < NUM_MEM_REGION; i++) {
		if ( (address >= MEM_REGIONS[i].begin) &&  ( address <= MEM_REGIONS[i].end) ) {
			uint32_t offset = address - MEM_REGIONS[i].begin;
			return (MEM_REGIONS[i].mem[offset+3] << 24) |
					(MEM_REGIONS[i].mem[offset+2] << 16) |
					(MEM_REGIONS[i].mem[offset+1] <<  8) |
					(MEM_REGIONS[i].mem[offset+0] <<  0);
		}
	}
	return 0;
}

/***************************************************************/
/* Write a 32-bit word to memory                                                                                */
/***************************************************************/
void mem_write_32(uint32_t address, uint32_t value)
{
	int i;
	uint32_t offset;
	for (i = 0; i < NUM_MEM_REGION; i++) {
		if ( (address >= MEM_REGIONS[i].begin) && (address <= MEM_REGIONS[i].end) ) {
			offset = address - MEM_REGIONS[i].begin;

			MEM_REGIONS[i].mem[offset+3] = (value >> 24) & 0xFF;
			MEM_REGIONS[i].mem[offset+2] = (value >> 16) & 0xFF;
			MEM_REGIONS[i].mem[offset+1] = (value >>  8) & 0xFF;
			MEM_REGIONS[i].mem[offset+0] = (value >>  0) & 0xFF;
		}
	}
}







void control_hazard() {
    // Extract registers from the instruction currently in the ID stage
    uint8_t rs1 = (IF_ID.IR >> 15) & BIT_MASK_5;
    uint8_t rs2 = (IF_ID.IR >> 20) & BIT_MASK_5;

    // Extract destination registers from instructions ahead in the pipeline
    uint8_t rd_ex = (ID_EX.IR >> 7) & BIT_MASK_5;
    uint8_t rd_mem = (EX_MEM.IR >> 7) & BIT_MASK_5;
    
    // Check if the instruction in EX is a LOAD
    uint8_t opcode_ex = GET_OPCODE(ID_EX.IR);

    bool hazard = false;

	//also check if rs1 or rs2 matches rd_wb (from the MEM_WB register
	uint8_t rd_wb = (MEM_WB.IR >> 7) & BIT_MASK_5;
	
    if (ENABLE_FORWARDING) {
        // CASE: Forwarding is ON
        // Only stall for a Load-Use hazard (data not ready until MEM stage)
        if (opcode_ex == LOAD_OPCODE) {
            if ((rd_ex != 0) && (rd_ex == rs1 || rd_ex == rs2)) {
                hazard = true;
            }
        }
    } else {
        // CASE: Forwarding is OFF
        // Stall for ANY dependency in EX or MEM stages
        bool hazard_rs1 = (rs1 != 0) && ((rs1 == rd_ex) || (rs1 == rd_mem));
        bool hazard_rs2 = (rs2 != 0) && ((rs2 == rd_ex) || (rs2 == rd_mem));
        
        if (hazard_rs1 || hazard_rs2) {
            hazard = true;
        }
    }

    if (hazard) {
        bubble = true;
        ID_EX.IR = 0;   // Insert NOP to "squash" the next stage
    } else {
        bubble = false;
    }
}
//forwarding function
// Forwarding function
void forward() {
    // 1. Extract source registers from the instruction currently in the EX stage (ID_EX)
    uint8_t rs1 = (ID_EX.IR >> 15) & BIT_MASK_5;
    uint8_t rs2 = (ID_EX.IR >> 20) & BIT_MASK_5;

    // 2. Extract destination registers from instructions in MEM and WB stages
    uint8_t rd_mem = (EX_MEM.IR >> 7) & BIT_MASK_5;
    uint8_t rd_wb = (MEM_WB.IR >> 7) & BIT_MASK_5;

    // 3. Check if instructions in MEM and WB actually write to a register
    uint8_t opcode_mem = GET_OPCODE(EX_MEM.IR);
    uint8_t opcode_wb = GET_OPCODE(MEM_WB.IR);

    bool mem_writes = (opcode_mem == R_OPCODE || opcode_mem == IMM_ALU_OPCODE || opcode_mem == LOAD_OPCODE);
    bool wb_writes = (opcode_wb == R_OPCODE || opcode_wb == IMM_ALU_OPCODE || opcode_wb == LOAD_OPCODE);

    // --- Forwarding for Source A ---
    // EX Hazard: Data is in the MEM stage (EX_MEM)
    if (mem_writes && rd_mem != 0 && rd_mem == rs1) {
        ID_EX.A = EX_MEM.ALUOutput;
    } 
    // MEM Hazard: Data is in the WB stage (MEM_WB)
    else if (wb_writes && rd_wb != 0 && rd_wb == rs1) {
        if (opcode_wb == LOAD_OPCODE) {
            ID_EX.A = MEM_WB.LMD; // For loads, data is in LMD
        } else {
            ID_EX.A = MEM_WB.ALUOutput;
        }
    }

    // --- Forwarding for Source B ---
    if (mem_writes && rd_mem != 0 && rd_mem == rs2) {
        ID_EX.B = EX_MEM.ALUOutput;
    } 
    else if (wb_writes && rd_wb != 0 && rd_wb == rs2) {
        if (opcode_wb == LOAD_OPCODE) {
            ID_EX.B = MEM_WB.LMD;
        } else {
            ID_EX.B = MEM_WB.ALUOutput;
        }
    }
}



/***************************************************************/
/* Execute one cycle                                                                                                              */
/***************************************************************/

void cycle() {
	if (CURRENT_STATE.PC >= MEM_TEXT_BEGIN + PROGRAM_SIZE * 4 + 24) {
		RUN_FLAG = FALSE;
		return;
	}

	if (MEMORY_STALL_CYCLES > 0) {
		MEMORY_STALL_CYCLES--;
		CYCLE_COUNT++;
		return;
	}

	control_hazard();
	if(ENABLE_FORWARDING){
		forward();
	}
	
	handle_pipeline();
	NEXT_STATE = CURRENT_STATE;
	CYCLE_COUNT++;
}






/***************************************************************/
/* Simulate RISCV for n cycles                                                                                       */
/***************************************************************/
void run(int num_cycles) {

	if (RUN_FLAG == FALSE) {
		printf("Simulation Stopped\n\n");
		return;
	}

	printf("Running simulator for %d cycles...\n\n", num_cycles);
	int i;
	for (i = 0; i < num_cycles; i++) {
		if (RUN_FLAG == FALSE) {
			printf("Simulation Stopped.\n\n");
			break;
		}
		cycle();
	}
}

/***************************************************************/
/* simulate to completion                                                                                               */
/***************************************************************/
void runAll() {
	if (RUN_FLAG == FALSE) {
		printf("Simulation Stopped.\n\n");
		return;
	}

	printf("Simulation Started...\n\n");
	while (RUN_FLAG){
		cycle();
	}
	printf("Simulation Finished.\n\n");
}

/***************************************************************/
/* Dump a word-aligned region of memory to the terminal                              */
/***************************************************************/
void mdump(uint32_t start, uint32_t stop) {
	uint32_t address;

	printf("-------------------------------------------------------------\n");
	printf("Memory content [0x%08x..0x%08x] :\n", start, stop);
	printf("-------------------------------------------------------------\n");
	printf("\t[Address in Hex (Dec) ]\t[Value]\n");
	for (address = start; address <= stop; address += 4){
		printf("\t0x%08x (%d) :\t0x%08x\n", address, address, mem_read_32(address));
	}
	printf("\n");
}

/***************************************************************/
/* Dump current values of registers to the teminal                                              */
/***************************************************************/
void rdump() {
	int i;
	printf("-------------------------------------\n");
	printf("Dumping Register Content\n");
	printf("-------------------------------------\n");
	printf("# Instructions Executed\t: %u\n", INSTRUCTION_COUNT);
	printf("PC\t: 0x%08x\n", CURRENT_STATE.PC);
	printf("-------------------------------------\n");
	printf("[Register]\t[Value]\n");
	printf("-------------------------------------\n");
	for (i = 0; i < RISCV_REGS; i++){
		printf("[R%d]\t: 0x%08x\n", i, CURRENT_STATE.REGS[i]);
	}
	printf("-------------------------------------\n");
	printf("[HI]\t: 0x%08x\n", CURRENT_STATE.HI);
	printf("[LO]\t: 0x%08x\n", CURRENT_STATE.LO);
	printf("-------------------------------------\n");
}

/***************************************************************/
/* Read a command from standard input.                                                               */
/***************************************************************/
void handle_command() {
	char buffer[20];
	uint32_t start, stop, cycles;
	uint32_t register_no;
	int register_value;
	int hi_reg_value, lo_reg_value;

	printf("MU-RISCV SIM:> ");

	if (scanf("%s", buffer) == EOF){
		exit(0);
	}

	switch(buffer[0]) {
		case 'S':
		case 's':
			if (buffer[1] == 'h' || buffer[1] == 'H'){
				show_pipeline();
			}else {
				runAll();
			}
			break;
		case 'M':
		case 'm':
			if (scanf("%x %x", &start, &stop) != 2){
				break;
			}
			mdump(start, stop);
			break;
		case '?':
			help();
			break;
		case 'Q':
		case 'q':
			printf("**************************\n");
			printf("Exiting MU-RISCV! Good Bye...\n");
			printf("**************************\n");
			exit(0);
		case 'R':
		case 'r':
			if (buffer[1] == 'd' || buffer[1] == 'D'){
				rdump();
			}else if(buffer[1] == 'e' || buffer[1] == 'E'){
				reset();
			}
			else {
				if (scanf("%d", &cycles) != 1) {
					break;
				}
				run(cycles);
			}
			break;
		case 'I':
		case 'i':
			if (scanf("%u %i", &register_no, &register_value) != 2){
				break;
			}
			CURRENT_STATE.REGS[register_no] = register_value;
			NEXT_STATE.REGS[register_no] = register_value;
			break;
		case 'H':
		case 'h':
			if (scanf("%i", &hi_reg_value) != 1){
				break;
			}
			CURRENT_STATE.HI = hi_reg_value;
			NEXT_STATE.HI = hi_reg_value;
			break;
		case 'L':
		case 'l':
			if (scanf("%i", &lo_reg_value) != 1){
				break;
			}
			CURRENT_STATE.LO = lo_reg_value;
			NEXT_STATE.LO = lo_reg_value;
			break;
		case 'P':
		case 'p':
			print_program();
			break;
		case 'F':
		case 'f':
			if(scanf("%d", &ENABLE_FORWARDING) != 1) {
				break;
			}
			else {
				ENABLE_FORWARDING == 0 ? printf("Forwarding OFF\n") : printf("Forwarding ON\n");
				break;
			}
		default:
			printf("Invalid Command.\n");
			break;
	}
}

/***************************************************************/
/* reset registers/memory and reload program                                                    */
/***************************************************************/
void reset() {
	int i;
	/*reset registers*/
	for (i = 0; i < RISCV_REGS; i++){
		CURRENT_STATE.REGS[i] = 0;
	}
	CURRENT_STATE.HI = 0;
	CURRENT_STATE.LO = 0;

	for (i = 0; i < NUM_MEM_REGION; i++) {
		uint32_t region_size = MEM_REGIONS[i].end - MEM_REGIONS[i].begin + 1;
		memset(MEM_REGIONS[i].mem, 0, region_size);
	}

	/*load program*/
	load_program();

	/*reset PC*/
	INSTRUCTION_COUNT = 0;
	CURRENT_STATE.PC =  MEM_TEXT_BEGIN;
	NEXT_STATE = CURRENT_STATE;
	RUN_FLAG = TRUE;
}

/***************************************************************/
/* Allocate and set memory to zero                                                                            */
/***************************************************************/
void init_memory() {
	int i;
	for (i = 0; i < NUM_MEM_REGION; i++) {
		uint32_t region_size = MEM_REGIONS[i].end - MEM_REGIONS[i].begin + 1;
		MEM_REGIONS[i].mem = malloc(region_size);
		memset(MEM_REGIONS[i].mem, 0, region_size);
	}
}

/**************************************************************/
/* load program into memory                                                                                      */
/**************************************************************/
void load_program() {
	FILE * fp;
	int i, word;
	uint32_t address;

	/* Open program file. */
	fp = fopen(prog_file, "r");
	if (fp == NULL) {
		printf("Error: Can't open program file %s\n", prog_file);
		exit(-1);
	}

	/* Read in the program. */

	i = 0;
	while( fscanf(fp, "%x\n", &word) != EOF ) {
		address = MEM_TEXT_BEGIN + i;
		mem_write_32(address, word);
		printf("writing 0x%08x into address 0x%08x (%d)\n", word, address, address);
		i += 4;
	}
	PROGRAM_SIZE = i/4;
	printf("Program loaded into memory.\n%d words written into memory.\n\n", PROGRAM_SIZE);
	fclose(fp);
}

















/************************************************************/
/* maintain the pipeline                                                                                           */
/************************************************************/
void handle_pipeline()
{
	/*INSTRUCTION_COUNT should be incremented when instruction is done*/
	/*Since we do not have branch/jump instructions, INSTRUCTION_COUNT should be incremented in WB stage */
	/* Work backwards because otherwise we would just be running instructions in sequential order, no pipeline. This allows for that "offset"*/

	WB();
	MEM();
	EX();
	
	if(!bubble) {
		ID();
		IF();
		
	}
	bubble = false;
	
	
}

/************************************************************/
/* writeback (WB) pipeline stage:                                                                          */
/************************************************************/
//Write to register file
//• For arithmetic ops, logic, shift, etc, load. What about stores?
//Update PC
//• For branches, jumps
void WB()
{
	uint32_t bincmd = MEM_WB.IR;
	if (!bincmd) return;
	uint8_t opcode = GET_OPCODE(MEM_WB.IR);
	uint8_t rd = (MEM_WB.IR >> 7) & BIT_MASK_5;

	switch (opcode) {
		case R_OPCODE:
		case IMM_ALU_OPCODE:
		case JAL_OPCODE:
		case JALR_OPCODE:
			if (rd != 0)
				CURRENT_STATE.REGS[rd] = MEM_WB.ALUOutput;
			INSTRUCTION_COUNT++;
			break;
		case LOAD_OPCODE:
			if (rd != 0)
				CURRENT_STATE.REGS[rd] = MEM_WB.LMD;
			INSTRUCTION_COUNT++;
			break;
		case STORE_OPCODE:
			INSTRUCTION_COUNT++;
			break;
		default:
			break;
			
	}
}

/************************************************************/
/* memory access (MEM) pipeline stage:                                                          */
/************************************************************/
//Used by load and store instructions only
//Other instructions will skip this stage
void MEM()
{
	uint32_t bincmd = EX_MEM.IR;
	if (!bincmd) { MEM_WB.IR = 0; return; }
	uint8_t opcode = GET_OPCODE(EX_MEM.IR);
	uint8_t funct3 = GET_FUNCT3(EX_MEM.IR);
	MEM_WB.IR = EX_MEM.IR;
	MEM_WB.ALUOutput = EX_MEM.ALUOutput;

	switch(opcode) {
		case LOAD_OPCODE: {
			uint32_t addr = EX_MEM.ALUOutput;
			printf("READ 0x%08x\n", addr);
			int penalty = 0;
			if (scanf("%d", &penalty) == 1 && penalty > 0) {
				MEMORY_STALL_CYCLES += penalty;
			}
			uint32_t word = mem_read_32(addr);
			switch(funct3) {
				case 0x0: {
					MEM_WB.LMD = (int32_t)(int8_t)(word & 0xFF); //LB - sign extend byte
					break;
				}
				case 0x1: { //LH - sign extend half word
					MEM_WB.LMD = (int32_t)(int16_t)(word & 0xFFFF);
					break;
				}
				case 0x2: { //LW - just read word
					MEM_WB.LMD = word;
					break;
				}
				case 0x4: { //LBU - zero extend byte
					MEM_WB.LMD = word & 0xFF;
					break;
				}
				case 0x5: { //LHU - zero extend half word
					MEM_WB.LMD = word & 0xFFFF;
					break;
				}
			}
			break;
		}
		case STORE_OPCODE: {
			uint32_t addr = EX_MEM.ALUOutput;
			printf("WRITE 0x%08x\n", addr);
			int penalty = 0;
			if (scanf("%d", &penalty) == 1 && penalty > 0) {
				MEMORY_STALL_CYCLES += penalty;
			}
			switch (funct3) {
				case 0x0: //sb
					mem_write_32(addr, EX_MEM.B & 0xFF);
					break;
				case 0x1: //sh
					mem_write_32(addr, EX_MEM.B & 0xFFFF);
					break;
				case 0x2: //sw
					mem_write_32(addr, EX_MEM.B);
					break;
			}
			break;
		}
		default: {
			MEM_WB.LMD = 0;
			break;
		}
	}
}

/************************************************************/
/* execution (EX) pipeline stage:                                                                          */
/************************************************************/
//Useful work done here (+, -, *, /), shift, logic
//operation, comparison (slt)
//Load/Store? lw x2, x3, 32 -> Compute address
void EX()
{
    uint32_t bincmd = ID_EX.IR;
    if (!bincmd) { EX_MEM.IR = 0; return; }
    uint8_t opcode = GET_OPCODE(ID_EX.IR);
    uint8_t funct3 = GET_FUNCT3(ID_EX.IR);
    uint8_t funct7 = (ID_EX.IR >> 25) & BIT_MASK_7;
    EX_MEM.IR = ID_EX.IR;
    EX_MEM.B = ID_EX.B;

    uint32_t operandA = ID_EX.A;
    uint32_t operandB = ID_EX.B;

    if (ENABLE_FORWARDING) {
        uint8_t exmem_rd = (EX_MEM.IR >> 7) & BIT_MASK_5;
        uint8_t memwb_rd = (MEM_WB.IR >> 7) & BIT_MASK_5;
        uint8_t id_ex_rs1 = (ID_EX.IR >> 15) & BIT_MASK_5;
        uint8_t id_ex_rs2 = (ID_EX.IR >> 20) & BIT_MASK_5;

        int exmem_regwrite = EX_MEM.IR &&
            (GET_OPCODE(EX_MEM.IR) == R_OPCODE ||
             GET_OPCODE(EX_MEM.IR) == IMM_ALU_OPCODE ||
             GET_OPCODE(EX_MEM.IR) == LOAD_OPCODE);

        int memwb_regwrite = MEM_WB.IR &&
            (GET_OPCODE(MEM_WB.IR) == R_OPCODE ||
             GET_OPCODE(MEM_WB.IR) == IMM_ALU_OPCODE ||
             GET_OPCODE(MEM_WB.IR) == LOAD_OPCODE);

        if (exmem_regwrite && exmem_rd != 0 && exmem_rd == id_ex_rs1)
            operandA = EX_MEM.ALUOutput;
        else if (memwb_regwrite && memwb_rd != 0 && memwb_rd == id_ex_rs1)
            operandA = (GET_OPCODE(MEM_WB.IR) == LOAD_OPCODE) ? MEM_WB.LMD : MEM_WB.ALUOutput;

        if (exmem_regwrite && exmem_rd != 0 && exmem_rd == id_ex_rs2)
            operandB = EX_MEM.ALUOutput;
        else if (memwb_regwrite && memwb_rd != 0 && memwb_rd == id_ex_rs2)
            operandB = (GET_OPCODE(MEM_WB.IR) == LOAD_OPCODE) ? MEM_WB.LMD : MEM_WB.ALUOutput;
        EX_MEM.B = operandB;
    }

    switch(opcode) {
        case R_OPCODE: {
            switch(funct3) {
                case 0x0: EX_MEM.ALUOutput = (funct7 == 0x20) ? operandA - operandB : operandA + operandB; break; //add/sub
                case 0x1: EX_MEM.ALUOutput = operandA << (operandB & 0x1F); break; //sll
                case 0x2: EX_MEM.ALUOutput = ((int32_t)operandA < (int32_t)operandB) ? 1 : 0; break; //slt
                case 0x3: EX_MEM.ALUOutput = (operandA < operandB) ? 1 : 0; break; //sltu
                case 0x4: EX_MEM.ALUOutput = operandA ^ operandB; break; //xor
                case 0x5: EX_MEM.ALUOutput = (funct7 == 0x20) //srl/sra
                    ? (uint32_t)((int32_t)operandA >> (operandB & 0x1F))
                    : operandA >> (operandB & 0x1F); break;
                case 0x6: EX_MEM.ALUOutput = operandA | operandB; break; //or
                case 0x7: EX_MEM.ALUOutput = operandA & operandB; break; //and
            }
            break;
        }
        case IMM_ALU_OPCODE: {
            switch(funct3) {
                case 0x0: EX_MEM.ALUOutput = operandA + ID_EX.imm; break; //addi
                case 0x1: EX_MEM.ALUOutput = operandA << (ID_EX.imm & 0x1F); break; //slli
                case 0x2: EX_MEM.ALUOutput = ((int32_t)operandA < (int32_t)ID_EX.imm) ? 1 : 0; break; //slti
                case 0x3: EX_MEM.ALUOutput = (operandA < ID_EX.imm) ? 1 : 0; break; //sltiu
                case 0x4: EX_MEM.ALUOutput = operandA ^ ID_EX.imm; break; //xori
                case 0x5: EX_MEM.ALUOutput = ((ID_EX.imm >> 10) & 0x1)  // srli/srai
                    ? (uint32_t)((int32_t)operandA >> (ID_EX.imm & 0x1F))
                    : operandA >> (ID_EX.imm & 0x1F); break;
                case 0x6: EX_MEM.ALUOutput = operandA | ID_EX.imm; break;  //ori
                case 0x7: EX_MEM.ALUOutput = operandA & ID_EX.imm; break;  //andi
            }
            break;
        }
        case LOAD_OPCODE:
        case STORE_OPCODE:
            EX_MEM.ALUOutput = operandA + ID_EX.imm; // Address calculation
            break;
		case BRANCH_OPCODE: {
			bool taken = false;
			switch(funct3) {
				case 0x0: taken = (operandA == operandB); break;  // beq
				case 0x1: taken = (operandA != operandB); break;  // bne
				case 0x4: taken = ((int32_t)operandA < (int32_t)operandB); break; // blt
				case 0x5: taken = ((int32_t)operandA >= (int32_t)operandB); break; // bge

			}
			if (taken) {
				// 1. Calculate Target
				uint32_t target_PC = ID_EX.PC + ID_EX.imm;
				
				// 2. Update PC
				CURRENT_STATE.PC = target_PC;
				
				// flush
				IF_ID.IR = 0;
				ID_EX.IR = 0; 
			}
			EX_MEM.ALUOutput = 0; // Branches don't write back
			break;
		}
		case JAL_OPCODE: {
			uint32_t target_PC = ID_EX.PC + ID_EX.imm;
			EX_MEM.ALUOutput = ID_EX.PC + 4;
			CURRENT_STATE.PC = target_PC;
			IF_ID.IR = 0; 
			ID_EX.IR = 0;
			break;
		}
		case JALR_OPCODE: {
			uint32_t target_PC = (operandA + ID_EX.imm) & ~1;
			EX_MEM.ALUOutput = ID_EX.PC + 4;
			CURRENT_STATE.PC = target_PC;
			IF_ID.IR = 0; 
			ID_EX.IR = 0;
			break;
		}
        default:
            EX_MEM.ALUOutput = 0;
            break;
    }




}

void ID()
{
    uint32_t bincmd = IF_ID.IR;
    if (!bincmd) { ID_EX.IR = 0; return; }
    uint8_t opcode = GET_OPCODE(bincmd);

    uint8_t rs1 = 0, rs2 = 0, rd = 0;

    //first pass. extract rs1/rs2 for hazard detection
    switch (opcode) {
        case R_OPCODE:
            rs1 = (bincmd >> 15) & BIT_MASK_5;
            rs2 = (bincmd >> 20) & BIT_MASK_5;
            break;
        case IMM_ALU_OPCODE:
        case LOAD_OPCODE:
        case JALR_OPCODE:
            rs1 = (bincmd >> 15) & BIT_MASK_5;
            break;
        case STORE_OPCODE:
            rs1 = (bincmd >> 15) & BIT_MASK_5;
            rs2 = (bincmd >> 20) & BIT_MASK_5;
            break;
        default:
            break;
    }

    int stall = 0;

    if (!ENABLE_FORWARDING) {
        uint8_t idex_rd = (ID_EX.IR  >> 7) & BIT_MASK_5;
        uint8_t exmem_rd = (EX_MEM.IR >> 7) & BIT_MASK_5;

        int idex_regwrite = ID_EX.IR  && (GET_OPCODE(ID_EX.IR) == R_OPCODE || GET_OPCODE(ID_EX.IR) == IMM_ALU_OPCODE || GET_OPCODE(ID_EX.IR) == LOAD_OPCODE);
        int exmem_regwrite = EX_MEM.IR && (GET_OPCODE(EX_MEM.IR) == R_OPCODE || GET_OPCODE(EX_MEM.IR) == IMM_ALU_OPCODE || GET_OPCODE(EX_MEM.IR) == LOAD_OPCODE);

        if (idex_regwrite && idex_rd != 0) {
            if ((rs1 != 0 && idex_rd == rs1) || (rs2 != 0 && idex_rd == rs2))
                stall = 1;
        }
        if (!stall && exmem_regwrite && exmem_rd != 0) {
            if ((rs1 != 0 && exmem_rd == rs1) || (rs2 != 0 && exmem_rd == rs2))
                stall = 1;
        }
    } else {
        uint8_t idex_rd = (ID_EX.IR >> 7) & BIT_MASK_5;
        int idex_is_load = ID_EX.IR && (GET_OPCODE(ID_EX.IR) == LOAD_OPCODE);
        if (idex_is_load && idex_rd != 0) {
            if ((rs1 != 0 && idex_rd == rs1) || (rs2 != 0 && idex_rd == rs2))
                stall = 1;
        }
    }

    if (stall) {
        ID_EX.IR = 0;
        ID_EX.A = 0;
        ID_EX.B = 0;
        ID_EX.imm = 0;
        bubble = true;
        return;
    }

    //if no hazard
    switch (opcode) {
        case R_OPCODE: {
            rd = (bincmd >> 7) & BIT_MASK_5;
            rs1 = (bincmd >> 15) & BIT_MASK_5;
            rs2 = (bincmd >> 20) & BIT_MASK_5;
            ID_EX.IR = IF_ID.IR;
            ID_EX.A = CURRENT_STATE.REGS[rs1];
            ID_EX.B = CURRENT_STATE.REGS[rs2];
            ID_EX.imm = 0;
            break;
        }
        case IMM_ALU_OPCODE: {
            uint32_t imm = (IF_ID.IR >> 20) & BIT_MASK_12;
            if (imm & 0x800) imm |= 0xFFFFF000; //sign extend
            rs1 = (IF_ID.IR >> 15) & BIT_MASK_5;
            ID_EX.IR= IF_ID.IR;
            ID_EX.A = CURRENT_STATE.REGS[rs1];
            ID_EX.B = 0;
            ID_EX.imm = imm;
            break;
        }
        case LOAD_OPCODE: {
            uint32_t imm = (IF_ID.IR >> 20) & BIT_MASK_12;
            if (imm & 0x800) imm |= 0xFFFFF000;
            rs1 = (IF_ID.IR >> 15) & BIT_MASK_5;
            ID_EX.IR= IF_ID.IR;
            ID_EX.A= CURRENT_STATE.REGS[rs1];
            ID_EX.B = 0;
            ID_EX.imm = imm;
            break;
        }
        case STORE_OPCODE: {
            uint8_t imm4 = (IF_ID.IR >> 7)  & BIT_MASK_5;
            uint8_t imm11 = (IF_ID.IR >> 25) & BIT_MASK_7;
            uint32_t imm = (imm11 << 5) | imm4;
            if (imm & 0x800) imm |= 0xFFFFF000;
            rs1 = (IF_ID.IR >> 15) & BIT_MASK_5;
            rs2 = (IF_ID.IR >> 20) & BIT_MASK_5;
            ID_EX.IR = IF_ID.IR;
            ID_EX.A= CURRENT_STATE.REGS[rs1];
            ID_EX.B = CURRENT_STATE.REGS[rs2];
            ID_EX.imm = imm;
            break;
        }
        case BRANCH_OPCODE: {
			// Decode the B-type immediate
			uint32_t imm12 = (IF_ID.IR >> 31) & 0x1;
			uint32_t imm10_5 = (IF_ID.IR >> 25) & 0x3F;
			uint32_t imm4_1 = (IF_ID.IR >> 8) & 0xF;
			uint32_t imm11 = (IF_ID.IR >> 7) & 0x1;
			
			int32_t imm = (imm12 << 12) | (imm11 << 11) | (imm10_5 << 5) | (imm4_1 << 1);
			if (imm & 0x1000) imm |= 0xFFFFE000; // Sign extend
			
			rs1 = (IF_ID.IR >> 15) & BIT_MASK_5;
			rs2 = (IF_ID.IR >> 20) & BIT_MASK_5;
			
			ID_EX.IR = IF_ID.IR;
			ID_EX.PC = IF_ID.PC;
			ID_EX.A = CURRENT_STATE.REGS[rs1];
			ID_EX.B = CURRENT_STATE.REGS[rs2];
			ID_EX.imm = imm;
			break;
		}

        case JAL_OPCODE: {
            uint32_t imm20 = (IF_ID.IR >> 31) & 0x1;
            uint32_t imm10_1 = (IF_ID.IR >> 21) & 0x3FF;
            uint32_t imm11 = (IF_ID.IR >> 20) & 0x1;
            uint32_t imm19_12 = (IF_ID.IR >> 12) & 0xFF;
            int32_t imm = (imm20 << 20) | (imm19_12 << 12) | (imm11 << 11) | (imm10_1 << 1);
            if (imm & 0x100000) imm |= 0xFFE00000;

            ID_EX.IR = IF_ID.IR;
            ID_EX.PC = IF_ID.PC;
            ID_EX.A = 0;
            ID_EX.B = 0;
            ID_EX.imm = imm;
            break;
        }
        case JALR_OPCODE: {
            uint32_t imm = (IF_ID.IR >> 20) & BIT_MASK_12;
            if (imm & 0x800) imm |= 0xFFFFF000;
            rs1 = (IF_ID.IR >> 15) & BIT_MASK_5;

            ID_EX.IR = IF_ID.IR;
            ID_EX.PC = IF_ID.PC;
            ID_EX.A = CURRENT_STATE.REGS[rs1];
            ID_EX.B = 0;
            ID_EX.imm = imm;
            break;
        }
        default:
            printf("Unknown command\n");
            break;
    }
} 

/************************************************************/
/* instruction fetch (IF) pipeline stage:                                                              */
/************************************************************/
void IF()
{
	// Fetch the instruction at the current PC.
	printf("READ 0x%08x\n", CURRENT_STATE.PC);
	int penalty = 0;
	if (scanf("%d", &penalty) == 1 && penalty > 0) {
		MEMORY_STALL_CYCLES += penalty;
	}

	IF_ID.IR = mem_read_32(CURRENT_STATE.PC);
	IF_ID.PC = CURRENT_STATE.PC;
	CURRENT_STATE.PC += 4;

    // Store the fetched instruction in the IR for the next state.

    // Increment the PC by 4 to point to the next instruction.

	
}


/************************************************************/
/* Initialize Memory                                                                                                    */
/************************************************************/
void initialize() {
	init_memory();
	CURRENT_STATE.PC = MEM_TEXT_BEGIN;
	NEXT_STATE = CURRENT_STATE;
	RUN_FLAG = TRUE;
}

/************************************************************/
/* Print the program loaded into memory (in RISCV assembly format)    */
/************************************************************/
void print_program(){
	/*IMPLEMENT THIS*/
	/* execute one instruction at a time. Use/update CURRENT_STATE and and NEXT_STATE, as necessary.*/
	
	for(uint32_t mem_tracer = MEM_TEXT_BEGIN; 
		mem_tracer < MEM_TEXT_BEGIN + PROGRAM_SIZE*4; 
		mem_tracer+=4) {
		uint32_t cmd = mem_read_32(mem_tracer);
		print_command(cmd);
		printf("\n");
	}
}

/************************************************************/
/* Print the instruction at given memory address (in RISCV assembly format)    */
/************************************************************/
void print_command(uint32_t bincmd) {
	if(bincmd) {
		uint8_t opcode = GET_OPCODE(bincmd);
		switch (opcode) {
			case R_OPCODE:
				handle_r_print(bincmd);
				break;
			case STORE_OPCODE:
				handle_s_print(bincmd);
				break;
			case IMM_ALU_OPCODE:
				handle_i_print(bincmd);
				break;
			case LOAD_OPCODE:
				handle_i_print(bincmd);
				break;
			case BRANCH_OPCODE:
				handle_b_print(bincmd);
				break;
			case JAL_OPCODE:
				handle_j_print(bincmd);
				break;
			case JALR_OPCODE: {
				uint8_t rd = bincmd >> 7 & BIT_MASK_5;
				uint8_t rs1 = bincmd >> 15 & BIT_MASK_5;
				uint16_t imm = bincmd >> 20 & BIT_MASK_12;
				print_i_type1_cmd("jalr", rd, rs1, imm);
				break;
			}
			default:
				printf("Unknown command!");
				break;
		}
	}
}

void handle_r_print(uint32_t bincmd) {
	uint8_t rd = bincmd >> 7 & BIT_MASK_5;
	uint8_t funct3 = bincmd >> 12 & BIT_MASK_3;
	uint8_t rs1 = bincmd >> 15 & BIT_MASK_5;
	uint8_t rs2 = bincmd >> 20 & BIT_MASK_5;
	uint8_t funct7 = bincmd >> 25 & BIT_MASK_7;
	switch(funct3) {
		case 0x0:
			switch(funct7){
				case 0x0:
					print_r_cmd("add", rd, rs1, rs2);
					break;
				case 0x20:
					print_r_cmd("sub", rd, rs1, rs2);
					break;
				default:
					printf("No funct7(%d) for funct3(%d) found for R-type.", funct7, funct3);
					break;
			}
			break;
		case 0x1:
			print_r_cmd("sll", rd, rs1, rs2);
			break;
		case 0x2:
			print_r_cmd("slt", rd, rs1, rs2);
			break;
		case 0x3:
			print_r_cmd("sltu", rd, rs1, rs2);
			break;
		case 0x4:
			print_r_cmd("xor", rd, rs1, rs2);
			break;
		case 0x5:
			switch(funct7){
				case 0x0:
					print_r_cmd("srl", rd, rs1, rs2);
					break;
				case 0x20:
					print_r_cmd("sra", rd, rs1, rs2);
					break;
				default:
					printf("No funct7(%d) for funct3(%d) found for R-type.", funct7, funct3);
					break;
			}
			break;
		case 0x6:
			print_r_cmd("or", rd, rs1, rs2);
			break;
		case 0x7:
			print_r_cmd("and", rd, rs1, rs2);
			break;
		default:
			printf("Unknown funct3(%d) in R-type", funct3);
			break;
	}
}

void handle_s_print(uint32_t bincmd) {
	uint8_t imm4 = bincmd >> 7 & BIT_MASK_5;
	uint8_t f3 = bincmd >> 12 & BIT_MASK_3;
	uint8_t rs1 = bincmd >> 15 & BIT_MASK_5;
	uint8_t rs2 = bincmd >> 20 & BIT_MASK_5;
	uint8_t imm11 = bincmd >> 25 & BIT_MASK_7;
	uint16_t imm = (imm11 | imm4);
	switch(f3) {
		case 0x0:
			print_s_cmd("sb", rs2, imm, rs1);
			break;
		case 0x1:
			print_s_cmd("sh", rs2, imm, rs1);
			break;
		case 0x2:
			print_s_cmd("sw", rs2, imm, rs1);
			break;
		default:
			printf("Unknown funct3(%d) in S type", f3);
			break;
	}
}

void handle_i_print(uint32_t bincmd) {

	uint8_t opcode = GET_OPCODE(bincmd);
	uint8_t rd = bincmd >> 7 & BIT_MASK_5;
	uint8_t funct3 = bincmd >> 12 & BIT_MASK_3;
	uint8_t rs1 = bincmd >> 15 & BIT_MASK_5;
	uint16_t imm = bincmd >> 20 & (BIT_MASK_12);
	switch(opcode) {
		case IMM_ALU_OPCODE:
			switch(funct3) {
				case 0x0: 
					print_i_type1_cmd("addi", rd, rs1, imm);
					break;
				case 0x1:
					print_i_type1_cmd("slli", rd, rs1, imm);
					break;
				case 0x2:
					print_i_type1_cmd("slti", rd, rs1, imm);
					break;
				case 0x3:
					print_i_type1_cmd("sltiu", rd, rs1, imm);
					break;
				case 0x4:
					print_i_type1_cmd("xori", rd, rs1, imm);
					break;
				case 0x5:
					;
					uint8_t imm5 = imm >> 5;
					switch(imm5){
						case 0:
							print_i_type1_cmd("srli", rd, rs1, imm);
							break;
						case 0x20:
							print_i_type1_cmd("srai", rd, rs1, imm);
							break;
						default:
							printf("Invalid imm[11:5](%d) for I-Type opcode(%d) funct3(%d)", imm5, opcode, funct3);
							break;
					}
					break;
				case 0x6:
					print_i_type1_cmd("ori", rd, rs1, imm);
					break;
				case 0x7:
					print_i_type1_cmd("andi", rd, rs1, imm);
					break;
				default:
					printf("Invalid funct3(%d) for I-type opcode(%d)", funct3, opcode);
					break;
			}
			break;
		case LOAD_OPCODE:
			switch(funct3){
				case 0x0:
					print_i_type2_cmd("lb", rd, rs1, imm);
					break;
				case 0x1:
					print_i_type2_cmd("lh", rd, rs1, imm);
					break;
				case 0x2:
					print_i_type2_cmd("lw", rd, rs1, imm);
					break;
				case 0x4:
					print_i_type2_cmd("lbu", rd, rs1, imm);
					break;
				case 0x5:
					print_i_type2_cmd("lhu", rd, rs1, imm);
					break;
				default:
					printf("Unknown funct3(%d) for I-type opcode(%d).", funct3, opcode);
					break;
			}
			break;
		default:
			printf("Unknown opcode(%d) for I-Type.", opcode);
			break;
	}

}

void handle_b_print(uint32_t bincmd) {
	// b type all gross...
	uint16_t scrambled_imm =(((bincmd >> 25) & BIT_MASK_7) << 5) | ((bincmd >> 7) & BIT_MASK_5);
	uint8_t bit12 = (scrambled_imm >> 12) & 0b1;
	uint8_t bit11 = scrambled_imm & 0b1;
	uint8_t bits10to5 = (scrambled_imm >> 5) & 0b111111;
	uint8_t bits4to1 = (scrambled_imm >> 1) & 0b1111;

	uint16_t imm = ((bit12 << 12) | (bit11 << 11) | (bits10to5 << 5) | (bits4to1 << 1)) >> 1; // >> 1 because it shifts left 1 in addressing to ensure even
	uint8_t f3 = bincmd >> 12 & BIT_MASK_3;
	uint8_t rs1 = bincmd >> 15 & BIT_MASK_5;
	uint8_t rs2 = bincmd >> 20 & BIT_MASK_5;

	switch(f3) {
		case 0x0:
			print_b_cmd("beq", rs1, rs2, imm);
			break;
		case 0x1:
			print_b_cmd("beq", rs1, rs2, imm);
			break;
		case 0x4:
			print_b_cmd("blt", rs1, rs2, imm);
			break;
		case 0x5:
			print_b_cmd("bge", rs1, rs2, imm);
			break;
		case 0x6:
			print_b_cmd("bltu", rs1, rs2, imm);
			break;
		case 0x7:
			print_b_cmd("bgeu", rs1, rs2, imm);
			break;
		default:
			printf("Unknown funct3(%d) in B type", f3);
			break;
	}

}

void handle_j_print(uint32_t bincmd) {
	uint8_t rd = (bincmd >> 7) & BIT_MASK_5;
	uint16_t scrambled_imm = (bincmd >> 12) & BIT_MASK_20;
	uint8_t bit20 = (scrambled_imm >> 20) & 0b1;
	uint16_t bits10to1 = (scrambled_imm >> 9) & 0b1111111111;
	uint8_t bit11 = (scrambled_imm >> 8) & 0b1; 
	uint8_t bits19to12 = (scrambled_imm) & 0b11111111;
	uint16_t offset = ((bit20 << 20) | (bits19to12 << 12) | (bit11 << 11) | (bits10to1 << 1)) >> 1;
	printf("jal x%d, %d", rd, offset);
}

void print_r_cmd(char* cmd_name, uint8_t rd, uint8_t rs1, uint8_t rs2) {
    printf("%s x%d, x%d, x%d", cmd_name, rd, rs1, rs2);
}

void print_s_cmd(char* cmd_name, uint8_t rs2, uint8_t offset, uint8_t rs1) {
    printf("%s x%d, %d(x%d)", cmd_name, rs2, offset, rs1);
}

void print_i_type1_cmd(char* cmd_name, uint8_t rd, uint8_t rs1, uint16_t imm) {
    printf("%s x%d, x%d, %d", cmd_name, rd, rs1, imm);
}

void print_i_type2_cmd(char* cmd_name, uint8_t rd, uint8_t rs1, uint16_t imm) {
    printf("%s x%d, %d(x%d)", cmd_name, rd, imm, rs1);
}

void print_b_cmd(char* cmd_name, uint8_t rs1, uint8_t rs2, uint16_t imm) {
	printf("%s x%d, x%d, %d", cmd_name, rs1, rs2, imm);
}

/************************************************************/
/* Print the current pipeline                                                                                    */
/************************************************************/
void show_pipeline()
{
	printf("Current PC: 0x%08x\n\n", CURRENT_STATE.PC);

	printf("IF -> ID:\n IR: "); print_command(IF_ID.IR); printf("\n");
	printf("ID -> EX:\n IR: "); print_command(ID_EX.IR); printf("\n A=0x%08x B=0x%08x imm=0x%08x\n", ID_EX.A, ID_EX.B, ID_EX.imm);
	printf("EX -> MEM:\n IR: "); print_command(EX_MEM.IR); printf("\n ALUOutput=0x%08x\n", EX_MEM.ALUOutput);
	printf("MEM -> WB:\n IR: "); print_command(MEM_WB.IR); printf("\n ALUOutput=0x%08x LMD=0x%08x\n", MEM_WB.ALUOutput, MEM_WB.LMD);
}

/***************************************************************/
/* main                                                                                                                                   */
/***************************************************************/
int main(int argc, char *argv[]) {
	setbuf(stdout, NULL);
	printf("\n**************************\n");
	printf("Welcome to MU-RISCV SIM...\n");
	printf("**************************\n\n");

	if (argc < 2) {
		printf("Error: You should provide input file.\nUsage: %s <input program> \n\n",  argv[0]);
		exit(1);
	}

	strcpy(prog_file, argv[1]);
	initialize();
	load_program();
	runAll();
	return 0;
}
