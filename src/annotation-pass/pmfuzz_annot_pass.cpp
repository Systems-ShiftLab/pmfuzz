#include <iostream>
#include <string>
#include <vector>

#include "pmfuzz_config.h"
#include "llvm/Pass.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/LegacyPassManager.h"
// #include "llvm/IR/TypeBuilder.h"
#include "llvm/Transforms/IPO/PassManagerBuilder.h"


// TODO: hint and function names can merge with a common header
// String of user annotation
#define PMReadAnnot "pmfuzz_pm_read_func"
#define PMWriteAnnot "pmfuzz_pm_write_func"
#define PMReadWriteAnnot "pmfuzz_pm_read_write_func"

// String of AFL hints
#define PMReadHint "pmfuzz_ro"
#define PMWriteHint "pmfuzz_wo"
#define PMReadWriteHint "pmfuzz_rw"

using namespace llvm;

namespace {

struct AnnotPass : public ModulePass {
  static char ID;
  AnnotPass() : ModulePass(ID) {}

  // Check if function has PM read attribute
  bool isPMReadFunc(Function* fn);

  // Check if function has PM write attribute
  bool isPMWriteFunc(Function* fn);

  // Create and insert hint functions
  CallInst* insertPMReadWriteHint(Module &M, BasicBlock &BB, std::string FuncName);

  // Assign attributes to each function in the module
  uint32_t annotAllFuncs(Module &M);

  // Label each BB with PM R/W functions for AFL
  uint32_t labelPMBasicBlock(Module &M, BasicBlock &BB);

  bool runOnModule(Module &M) override;
}; // end of AnnotPass

bool AnnotPass::isPMReadFunc(Function* fn) 
{
  return (fn->hasFnAttribute(PMReadAnnot)         
          || fn->hasFnAttribute(PMReadWriteAnnot));
}

bool AnnotPass::isPMWriteFunc(Function* fn)
{
  return (fn->hasFnAttribute(PMWriteAnnot) 
          || fn->hasFnAttribute(PMReadWriteAnnot));
}
}  // end of anonymous namespace

CallInst* AnnotPass::insertPMReadWriteHint(Module &M, 
                        BasicBlock &BB, std::string FuncName)
{
    // Get context
    LLVMContext &ctx = M.getContext();
    // Create Function
    Function *insertFunc = cast<Function>(M.getOrInsertFunction(FuncName, 
                                  FunctionType::getVoidTy(ctx), 
                                  Type::getInt32Ty(ctx)).getCallee());
    assert(insertFunc);
    // Create arguments
    std::vector<Value *> arglist;
    int val = rand();
    Value *arg0 = ConstantInt::get(IntegerType::get(M.getContext(), 32), val);
    arglist.push_back(arg0);

    // Insert to the beginning of the BB
    CallInst *insertCallInstr = CallInst::Create(insertFunc, 
                            ArrayRef<Value *>(arglist), "", 
                            cast<Instruction>(BB.getFirstInsertionPt()));
    assert(insertCallInstr);
    return insertCallInstr;
}

uint32_t AnnotPass::annotAllFuncs(Module &M)
{
  uint32_t annotCount = 0;
  // Source: http://bholt.org/posts/llvm-quick-tricks.html
  // Get annotation metadata
  auto global_annos = M.getNamedGlobal("llvm.global.annotations");
  if (global_annos) {
    auto a = cast<ConstantArray>(global_annos->getOperand(0));
    for (int i=0; i<a->getNumOperands(); i++) {
      auto e = cast<ConstantStruct>(a->getOperand(i));

      if (Function* fn = cast<Function>(e->getOperand(0)->getOperand(0))) {
        auto anno = cast<ConstantDataArray>(cast<GlobalVariable>
            (e->getOperand(1)->getOperand(0))->getOperand(0))->getAsCString();
        // Function annotation
        annotCount++;
        fn->addFnAttr(anno);
        // Debug: print out annotation
        // errs() << *fn << " " << anno << "\n";
      }
    }
  }
  return annotCount;
}

uint32_t AnnotPass::labelPMBasicBlock(Module &M, BasicBlock &BB) 
{
  uint32_t BBhasPMReadFunc = 0, BBhasPMWriteFunc = 0;
  // Check if any function call has PM read/write attribute
  for (auto &I : BB) {
    // Find Call and Invoke insturctions
    Function *CalledFunc = NULL;
    Value* CalledValue = NULL;
    if (isa<CallInst>(&I)) {
      CalledFunc = cast<CallInst>(&I)->getCalledFunction(); 
      if (!CalledFunc) { // Handle indirect calls
        CalledValue = cast<CallInst>(&I)->getCalledValue();
      }
    } else if (isa<InvokeInst>(&I)) {
      // errs() << I << "\n";
      // TODO: Need to test invoke
      CalledFunc = cast<InvokeInst>(&I)->getCalledFunction();
      if (!CalledFunc) { // Handle indirect calls
        CalledValue = cast<InvokeInst>(&I)->getCalledValue(); 
      }
    }
    // errs() << "@ " << __LINE__ << I << "\n";

    // Convert indirect calls
    if (!CalledFunc && CalledValue) {
      if (isa<LoadInst>(CalledValue) || isa<StoreInst>(CalledValue)) {
        // TOOD: handle function pointers
      } else if (isa<BitCastInst>(CalledValue)) {
        // errs() << "@ " << __LINE__ << CalledValue->stripPointerCasts()->getValueName() << "\n";
        // Convert indirect calls with bitcast to functions
        if (CalledValue->stripPointerCasts()->getValueName()) {
          // errs() << "@ " << __LINE__ << I << "\n";
          // CalledFunc = cast<Function>(CalledValue->stripPointerCasts());
        }
      } else {
          CalledFunc = cast<Function>(CalledValue->stripPointerCasts());
      }
    }

    // Check if called function performs PM read/write
    if (CalledFunc) {
      BBhasPMReadFunc += isPMReadFunc(CalledFunc); 
      BBhasPMWriteFunc += isPMWriteFunc(CalledFunc);
    }
  }
  // Inject AFL hints
  if (BBhasPMReadFunc && BBhasPMWriteFunc) { // PM read + write hint
    insertPMReadWriteHint(M, BB, PMReadWriteHint);
  } else if (BBhasPMReadFunc) { // PM read hint
    insertPMReadWriteHint(M, BB, PMReadHint);
  } else if (BBhasPMWriteFunc) { // PM write hint
    insertPMReadWriteHint(M, BB, PMWriteHint);
  }
  // Return true if hints are inserted
  return BBhasPMReadFunc + BBhasPMWriteFunc;
}

bool AnnotPass::runOnModule(Module &M) 
{
  srand(0);
  uint32_t modifyCount = 0;

  errs() << "+++ \x1b[0;36m" << PMFUZZ_NAME << "\x1b[0m" 
            << "\x1b[1;97m" << " Annotation Pass" << "\x1b[0m" 
            << " v" << PMFUZZ_VERSION << " by " 
            << PMFUZZ_AUTHORS << " +++" << "\n";

  // Attach attributes to PM read/write functions
  uint32_t annotCount = annotAllFuncs(M);
  errs() << "Annotated " << "\x1b[1;97m" << annotCount << "\x1b[0m" 
            << " function(s)\n";

  // Insert PM read/write hint functions
  int readFuns = 0, writeFuns = 0;
  for (auto &F : M) {
    // For debugging: Print function names and properties
    readFuns += isPMReadFunc(&F);
    writeFuns += isPMWriteFunc(&F);
    // errs() << F.getName() << "\n";
    for (auto &BB : F) {
      modifyCount += labelPMBasicBlock(M, BB);
    }
  }

  errs() << "Found " << "\x1b[1;97m" << readFuns << "\x1b[0m" 
         << " read annotation(s) and " << "\x1b[1;97m" << writeFuns << "\x1b[0m" 
         << " write annotation(s)." << " Modified? " 
         << (modifyCount ? "\x1b[1;92mYes" : "\x1b[1;93mNo") << "\x1b[0m" 
         << " (" << modifyCount << " BB)" << "\n";
  
  return (bool)modifyCount; // Return true if this pass has modified IR
}

char AnnotPass::ID = 0;
static RegisterPass<AnnotPass> X("AnnotPass", "Annotation pass",
                              false /* Only looks at CFG */,
                              false /* Analysis Pass */);

static void loadPass(const PassManagerBuilder &,
                          legacy::PassManagerBase &PM) {
    PM.add(new AnnotPass());
}
static RegisterStandardPasses clangtoolLoader_Ox(PassManagerBuilder::EP_OptimizerLast, loadPass);
static RegisterStandardPasses clangtoolLoader_O0(PassManagerBuilder::EP_EnabledOnOptLevel0, loadPass);
// Usage: clang -Xclang -load -Xclang <path to pass> <the rest of the original command>