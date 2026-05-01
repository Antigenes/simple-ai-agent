import sys
import os
import tempfile
import subprocess
import re

# 强制 UTF-8（兼容中文 Windows）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ==================== 配置区 ====================
# 🔑 为了安全，请将 Key 替换为你自己的 DashScope API Key
DASHSCOPE_API_KEY = "sk-e6ce08b96837482f8a5ef61e57b3b3cc"

# 📌 选择模型（推荐 Turbo：便宜+快）
MODEL_NAME = "qwen-turbo"

# 初始化 DashScope
try:
    import dashscope
    dashscope.api_key = DASHSCOPE_API_KEY
except ImportError:
    print("❌ 缺少依赖！请运行：pip install dashscope", file=sys.stderr)
    sys.exit(1)

# ==================== 调用 Qwen API ====================
def call_qwen(prompt: str) -> str | None:
    from dashscope import Generation
    try:
        response = Generation.call(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2048,
            result_format="text"
        )
        if response.status_code == 200:
            return response.output.text.strip()
        else:
            print(f"⚠️ Qwen API 错误: {response.code} - {response.message}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"⚠️ 调用 Qwen 失败: {e}", file=sys.stderr)
        return None

# ==================== 安全运行 C++ 代码 ====================
def run_cpp_code(code: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False, encoding='utf-8') as f:
        f.write(code)
        cpp_path = f.name

    exe_path = cpp_path.replace('.cpp', '.exe' if os.name == 'nt' else '.out')
    
    try:
        compile_result = subprocess.run(
            ['g++', '-std=c++17', '-O2', '-Wall', cpp_path, '-o', exe_path],
            capture_output=True,
            timeout=15
        )
        
        if compile_result.returncode != 0:
            stderr = compile_result.stderr.decode('utf-8', errors='replace')
            return False, f"Compile Error:\n{stderr}"
        
        run_result = subprocess.run([exe_path], capture_output=True, timeout=10)
        
        if run_result.returncode != 0:
            output = (run_result.stderr or run_result.stdout).decode('utf-8', errors='replace')
            return False, f"Runtime Error (exit {run_result.returncode}):\n{output}"
        
        stdout = run_result.stdout.decode('utf-8', errors='replace')
        return True, f"Output:\n{stdout}"
    
    except subprocess.TimeoutExpired:
        return False, "Error: Timeout during compilation or execution."
    except FileNotFoundError:
        return False, "Error: g++ not found. Please install GCC/MinGW."
    except Exception as e:
        return False, f"Unexpected error: {e}"
    finally:
        for path in (cpp_path, exe_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

# ==================== 提取 C++ 代码 ====================
def extract_code(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"```(?:cpp|c\+\+)?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()

# ==================== Debug Agent ====================
def debug_agent(buggy_code: str) -> str | None:
    current = buggy_code
    max_tries = 3
    print("\n--- 🛠️ C++ Debug Agent (Qwen) Started ---")
    
    for attempt in range(1, max_tries + 1):
        print(f"\n[尝试 {attempt}/{max_tries}] 编译并运行...")
        success, output = run_cpp_code(current)
        
        if success:
            print("✅ 修复成功！代码已正常运行。")
            return current
        
        print("❌ 发现错误，请求 Qwen 修复...")
        prompt = f"""
你是一名资深 C++ 开发专家，请修复以下代码中的错误。
要求：
- 修复内存错误（未分配内存、野指针、浅拷贝）、数组越界、语法错误等
- 动态数组必须用 new[] / delete[]（禁止混用 malloc/free）
- 循环边界正确（例如 length=5 → 索引 0~4）
- 保留原始逻辑意图
- 只输出完整、可独立编译的 C++ 代码，不要解释，不要写 ```cpp

错误信息：
{output}

当前代码：
{current}
"""
        reply = call_qwen(prompt)
        if reply:
            current = extract_code(reply)
            print("🔧 收到修复建议，重试中...")
        else:
            print("💥 无法获取 Qwen 响应，终止调试。")
            break
    return None

# ==================== 主程序 ====================
def main():
    print("🔍 请输入 C++ 代码（多行），输入 '# END' 结束：\n")
    lines = []
    try:
        while True:
            line = input()
            if line.strip() == "# END":
                break
            lines.append(line)
    except KeyboardInterrupt:
        print("\n用户中断。")
        return
    
    if not lines:
        print("❌ 无输入，退出。")
        return
    
    code = "\n".join(lines)
    print("\n🚀 开始调试：")
    print("-" * 50)
    print(code)
    print("-" * 50)
    
    fixed = debug_agent(code)
    
    if fixed:
        print("\n🎉 最终修复代码：")
        print("=" * 60)
        print(fixed)
        print("=" * 60)
        print("\n▶️ 验证运行结果：")
        _, result = run_cpp_code(fixed)
        print(result)
    else:
        print("\n💀 调试失败：无法修复代码。")

if __name__ == "__main__":
    main()