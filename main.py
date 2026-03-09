import os
import sys
import json
import base64
import subprocess
import re
import shutil
import time

try:
    from openai import OpenAI
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai"])
    from openai import OpenAI

BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

LOGO = r"""
 /$$                                /$$$$$$                  /$$          
| $$                               /$$__  $$                | $$          
| $$        /$$$$$$  /$$  /$$  /$$| $$  \__/  /$$$$$$   /$$$$$$$  /$$$$$$ 
| $$       /$$__  $$| $$ | $$ | $$| $$       /$$__  $$ /$$__  $$ /$$__  $$
| $$      | $$  \ $$| $$ | $$ | $$| $$      | $$  \ $$| $$  | $$| $$$$$$$$
| $$      | $$  | $$| $$ | $$ | $$| $$    $$| $$  | $$| $$  | $$| $$_____/
| $$$$$$$$|  $$$$$$/|  $$$$$/$$$$/|  $$$$$$/|  $$$$$$/|  $$$$$$$|  $$$$$$$
|________/ \______/  \_____/\___/  \______/  \______/  \_______/ \_______/
"""

VERSION = "1.0"

SYSTEM_PROMPT = """You are LowCode AI assistant. You help users manage their project files and folders.

You MUST respond ONLY with a valid JSON object. No text before or after the JSON.

The JSON must have this structure:
{
  "thinking": "your reasoning about what to do",
  "actions": [
    {
      "type": "action_type",
      ...action specific fields...
    }
  ],
  "summary": "brief human-readable summary of what you did"
}

Available action types:

1. read_file - Read a file
   {"type": "read_file", "path": "relative/path"}

2. create_file - Create a new file
   {"type": "create_file", "path": "relative/path", "content": "file content"}

3. edit_file - Edit/overwrite a file
   {"type": "edit_file", "path": "relative/path", "content": "new full content", "added": 5, "removed": 2}

4. delete_file - Delete a file
   {"type": "delete_file", "path": "relative/path"}

5. create_folder - Create a folder
   {"type": "create_folder", "path": "relative/path"}

6. delete_folder - Delete a folder
   {"type": "delete_folder", "path": "relative/path"}

7. list_folder - List folder contents
   {"type": "list_folder", "path": "relative/path"}

8. run_command - Run a shell command (ONLY within the project directory)
   {"type": "run_command", "command": "command to run"}

9. read_base64 - Read an image/audio/binary file as base64
   {"type": "read_base64", "path": "relative/path"}

10. message - Just send a message to the user
    {"type": "message", "text": "your message"}

IMPORTANT RULES:
- All paths MUST be relative to the project root. NEVER use absolute paths.
- NEVER access files outside the project directory.
- NEVER run destructive system commands (rm -rf /, anything with system32, etc.)
- Commands are restricted to the project directory.
- For binary files (images, audio, etc.), use read_base64.
- When editing files, provide the COMPLETE new file content.
- You can chain multiple actions in one response.
- If you need to see the project structure first, use list_folder with path "."
- Always respond in the same language the user writes to you.
- ONLY output JSON. No markdown, no code blocks, no extra text.
"""


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_logo():
    print(f"{BLUE}{BOLD}{LOGO}{RESET}")
    print(f"               {WHITE}{BOLD}Lowcode{RESET}")
    print()
    print(f"               {WHITE}version:{VERSION}{RESET}")
    print()
    print(f"               by {BLUE}{BOLD}@req_dev{RESET}")
    print()


def print_logo_with_info(repo, model, api_key):
    print(f"{BLUE}{BOLD}{LOGO}{RESET}")
    print(f"               {WHITE}{BOLD}Lowcode{RESET}")
    print()
    print(f"               {WHITE}version:{VERSION}{RESET}")
    print()
    print(f"               by {BLUE}{BOLD}@req_dev{RESET}")
    print()
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"  {CYAN}📁 Repository:{RESET} {WHITE}{repo}{RESET}")
    print(f"  {CYAN}🤖 Model:{RESET}      {WHITE}{model}{RESET}")
    print(f"  {CYAN}🔑 API Key:{RESET}    {WHITE}{masked_key}{RESET}")
    print()
    print(f"  {DIM}{'─' * 60}{RESET}")
    print()


def is_path_safe(base_path, target_path):
    base = os.path.realpath(base_path)
    target = os.path.realpath(os.path.join(base_path, target_path))
    return target.startswith(base)


def is_command_safe(command, repo_path):
    dangerous_patterns = [
        "system32", "System32", "SYSTEM32",
        "rm -rf /", "rm -rf /*",
        "format c:", "format C:",
        "del /f /s /q c:", "del /f /s /q C:",
        "mkfs", ":(){:|:&};:",
        "dd if=", "> /dev/sda",
        "chmod -R 777 /",
        "chown -R",
        "sudo rm",
    ]
    for pattern in dangerous_patterns:
        if pattern in command:
            return False
    return True


def execute_actions(actions, repo_path):
    results = []

    for action in actions:
        action_type = action.get("type", "unknown")

        try:
            if action_type == "read_file":
                path = action.get("path", "")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "read_file", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    print(f"  {CYAN}[📖] Read {path} ({len(content)} chars){RESET}")
                    results.append({"action": "read_file", "path": path, "content": content})
                else:
                    print(f"  {RED}[✗] File not found: {path}{RESET}")
                    results.append({"action": "read_file", "path": path, "error": "File not found"})

            elif action_type == "create_file":
                path = action.get("path", "")
                content = action.get("content", "")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "create_file", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                parent_dir = os.path.dirname(full_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                lines = content.count('\n') + (1 if content else 0)
                print(f"  {GREEN}[+] Created {path} ({lines} lines){RESET}")
                results.append({"action": "create_file", "path": path, "success": True})

            elif action_type == "edit_file":
                path = action.get("path", "")
                content = action.get("content", "")
                added = action.get("added", "?")
                removed = action.get("removed", "?")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "edit_file", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                parent_dir = os.path.dirname(full_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  {YELLOW}[✎] Edited {path} (+{added} -{removed}){RESET}")
                results.append({"action": "edit_file", "path": path, "success": True})

            elif action_type == "delete_file":
                path = action.get("path", "")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "delete_file", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"  {RED}[🗑] Deleted {path}{RESET}")
                    results.append({"action": "delete_file", "path": path, "success": True})
                else:
                    print(f"  {RED}[✗] File not found: {path}{RESET}")
                    results.append({"action": "delete_file", "path": path, "error": "File not found"})

            elif action_type == "create_folder":
                path = action.get("path", "")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "create_folder", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                os.makedirs(full_path, exist_ok=True)
                print(f"  {GREEN}[📁+] Created folder {path}{RESET}")
                results.append({"action": "create_folder", "path": path, "success": True})

            elif action_type == "delete_folder":
                path = action.get("path", "")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "delete_folder", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                if os.path.exists(full_path):
                    shutil.rmtree(full_path)
                    print(f"  {RED}[📁🗑] Deleted folder {path}{RESET}")
                    results.append({"action": "delete_folder", "path": path, "success": True})
                else:
                    print(f"  {RED}[✗] Folder not found: {path}{RESET}")
                    results.append({"action": "delete_folder", "path": path, "error": "Folder not found"})

            elif action_type == "list_folder":
                path = action.get("path", ".")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "list_folder", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                if os.path.exists(full_path):
                    items = []
                    for item in os.listdir(full_path):
                        item_path = os.path.join(full_path, item)
                        if os.path.isdir(item_path):
                            items.append(f"📁 {item}/")
                        else:
                            size = os.path.getsize(item_path)
                            items.append(f"📄 {item} ({size}b)")
                    print(f"  {CYAN}[📂] Listed {path}/ ({len(items)} items){RESET}")
                    for item in items:
                        print(f"       {DIM}{item}{RESET}")
                    results.append({"action": "list_folder", "path": path, "items": items})
                else:
                    print(f"  {RED}[✗] Folder not found: {path}{RESET}")
                    results.append({"action": "list_folder", "path": path, "error": "Folder not found"})

            elif action_type == "run_command":
                command = action.get("command", "")
                if not is_command_safe(command, repo_path):
                    print(f"  {RED}[✗] Dangerous command blocked: {command}{RESET}")
                    results.append({"action": "run_command", "command": command, "error": "Command blocked for safety"})
                    continue

                print(f"  {MAGENTA}[⚡] Running: {command}{RESET}")
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    output = result.stdout
                    error = result.stderr
                    if output:
                        for line in output.split('\n')[:20]:
                            print(f"       {DIM}{line}{RESET}")
                        if output.count('\n') > 20:
                            print(f"       {DIM}... (truncated){RESET}")
                    if error:
                        for line in error.split('\n')[:10]:
                            print(f"       {RED}{line}{RESET}")
                    print(f"  {MAGENTA}[⚡] Exit code: {result.returncode}{RESET}")
                    results.append({
                        "action": "run_command",
                        "command": command,
                        "stdout": output[:5000],
                        "stderr": error[:2000],
                        "exit_code": result.returncode
                    })
                except subprocess.TimeoutExpired:
                    print(f"  {RED}[✗] Command timed out (60s){RESET}")
                    results.append({"action": "run_command", "command": command, "error": "Timeout"})

            elif action_type == "read_base64":
                path = action.get("path", "")
                if not is_path_safe(repo_path, path):
                    print(f"  {RED}[✗] Access denied: {path} is outside project{RESET}")
                    results.append({"action": "read_base64", "path": path, "error": "Path outside project"})
                    continue

                full_path = os.path.join(repo_path, path)
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        data = base64.b64encode(f.read()).decode('utf-8')
                    size = os.path.getsize(full_path)
                    print(f"  {CYAN}[🔍] Read binary {path} ({size}b → base64){RESET}")
                    if len(data) > 10000:
                        data_preview = data[:10000] + "...(truncated)"
                    else:
                        data_preview = data
                    results.append({"action": "read_base64", "path": path, "base64": data_preview})
                else:
                    print(f"  {RED}[✗] File not found: {path}{RESET}")
                    results.append({"action": "read_base64", "path": path, "error": "File not found"})

            elif action_type == "message":
                text = action.get("text", "")
                print(f"  {WHITE}[💬] {text}{RESET}")
                results.append({"action": "message", "text": text})

            else:
                print(f"  {RED}[?] Unknown action: {action_type}{RESET}")
                results.append({"action": action_type, "error": "Unknown action type"})

        except Exception as e:
            print(f"  {RED}[✗] Error executing {action_type}: {str(e)}{RESET}")
            results.append({"action": action_type, "error": str(e)})

    return results


def parse_ai_response(response_text):
    text = response_text.strip()

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    brace_start = text.find('{')
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    text = text[brace_start:i + 1]
                    break

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def main():
    clear_screen()
    print_logo()

    api_key = input(f"  {WHITE}Введите свой OnlySq API ключ(my.onlysq.ru): {RESET}").strip()
    if not api_key:
        print(f"  {RED}API ключ не может быть пустым!{RESET}")
        sys.exit(1)

    print()

    while True:
        model_id = input(f"  {WHITE}Введите ID желаемой модели(https://docs.onlysq.ru/#models): {RESET}").strip()
        if not model_id:
            print(f"  {RED}ID модели не может быть пустым!{RESET}")
            continue

        print()
        print(f"  {YELLOW}Проверяем работоспособность модели с вашим ключом...{RESET}")
        print()

        try:
            client = OpenAI(api_key=api_key, base_url="https://api.onlysq.ru/ai/openai/")
            messages = [{"role": "user", "content": "Привет"}]

            test_response = ""
            r = client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=True
            )

            for chunk in r:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    test_response += chunk.choices[0].delta.content

            if test_response:
                print(f"  {GREEN}[✓] Модель работает! Ответ: {test_response[:80]}...{RESET}")
                print()
                break
            else:
                print(f"  {RED}[✗] Модель вернула пустой ответ.{RESET}")
                with open("error.txt", "w", encoding="utf-8") as f:
                    f.write("Model returned empty response")
                print(f"  {RED}Ошибка модели. Текст ошибки сохранен в файл error.txt{RESET}")
                print()

        except Exception as e:
            error_text = str(e)
            with open("error.txt", "w", encoding="utf-8") as f:
                f.write(error_text)
            print(f"  {RED}Ошибка модели. Текст ошибки сохранен в файл error.txt{RESET}")
            print()

    repo_input = input(f"  {WHITE}Укажите ПОЛНЫЙ путь репозитория вашего проекта: {RESET}").strip()
    if not repo_input:
        print(f"  {RED}Путь не может быть пустым!{RESET}")
        sys.exit(1)

    repo_path = os.path.realpath(os.path.expanduser(repo_input))

    if not os.path.isdir(repo_path):
        print(f"  {YELLOW}Папка не найдена, создаём: {repo_path}{RESET}")
        os.makedirs(repo_path, exist_ok=True)

    os.chdir(repo_path)

    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n\nProject root directory: {repo_path}\nAll file paths are relative to this directory."}
    ]

    while True:
        clear_screen()
        print_logo_with_info(repo_path, model_id, api_key)

        user_input = input(f"  {GREEN}{BOLD}Enter your AI request: {RESET}").strip()

        if not user_input:
            continue

        if user_input.lower() in ['exit', 'quit', 'выход']:
            print(f"\n  {BLUE}До свидания! 👋{RESET}\n")
            break

        project_tree = []
        try:
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]
                level = root.replace(repo_path, '').count(os.sep)
                indent = '  ' * level
                folder_name = os.path.basename(root)
                project_tree.append(f"{indent}📁 {folder_name}/")
                sub_indent = '  ' * (level + 1)
                for file in files[:50]:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                    except:
                        size = 0
                    project_tree.append(f"{sub_indent}📄 {file} ({size}b)")
                if len(files) > 50:
                    project_tree.append(f"{sub_indent}... and {len(files) - 50} more files")
        except Exception:
            project_tree = ["(unable to read project structure)"]

        tree_str = '\n'.join(project_tree[:200])

        enhanced_prompt = f"""User request: {user_input}

Current project structure:
{tree_str}

Remember: respond ONLY with valid JSON. All paths must be relative to the project root."""

        conversation.append({"role": "user", "content": enhanced_prompt})

        print()
        print(f"  {YELLOW}⏳ Thinking...{RESET}")
        print()

        try:
            client = OpenAI(api_key=api_key, base_url="https://api.onlysq.ru/ai/openai/")

            full_response = ""
            r = client.chat.completions.create(
                model=model_id,
                messages=conversation,
                stream=True
            )

            for chunk in r:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content

            if not full_response.strip():
                print(f"  {RED}[✗] AI returned empty response{RESET}")
                conversation.pop()
                input(f"\n  {DIM}Press Enter to continue...{RESET}")
                continue

            parsed = parse_ai_response(full_response)

            if parsed is None:
                print(f"  {RED}[✗] Failed to parse AI response as JSON{RESET}")
                print(f"  {DIM}Raw response:{RESET}")
                print(f"  {DIM}{full_response[:500]}{RESET}")
                conversation.append({"role": "assistant", "content": full_response})
                conversation.append({"role": "user", "content": "Your response was not valid JSON. Please respond ONLY with a valid JSON object as specified in the system prompt."})
                input(f"\n  {DIM}Press Enter to continue...{RESET}")
                continue

            thinking = parsed.get("thinking", "")
            if thinking:
                print(f"  {DIM}💭 {thinking}{RESET}")
                print()

            actions = parsed.get("actions", [])
            if actions:
                print(f"  {BOLD}Executing {len(actions)} action(s):{RESET}")
                print()
                action_results = execute_actions(actions, repo_path)
            else:
                action_results = []

            summary = parsed.get("summary", "")
            if summary:
                print()
                print(f"  {GREEN}{BOLD}✅ {summary}{RESET}")

            conversation.append({"role": "assistant", "content": full_response})

            read_results = [r for r in action_results if r.get("content") or r.get("base64") or r.get("items") or r.get("stdout")]
            if read_results:
                feedback = f"Action results:\n{json.dumps(read_results, ensure_ascii=False, indent=2)[:8000]}"
                conversation.append({"role": "user", "content": feedback + "\n\nIf you need to take more actions based on these results, respond with JSON. If everything is done, respond with a JSON containing just a message action."})

                print()
                print(f"  {YELLOW}⏳ Processing results...{RESET}")

                full_response2 = ""
                r2 = client.chat.completions.create(
                    model=model_id,
                    messages=conversation,
                    stream=True
                )
                for chunk in r2:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        full_response2 += chunk.choices[0].delta.content

                if full_response2.strip():
                    parsed2 = parse_ai_response(full_response2)
                    if parsed2:
                        actions2 = parsed2.get("actions", [])
                        if actions2:
                            print()
                            print(f"  {BOLD}Executing {len(actions2)} follow-up action(s):{RESET}")
                            print()
                            execute_actions(actions2, repo_path)

                        summary2 = parsed2.get("summary", "")
                        if summary2:
                            print()
                            print(f"  {GREEN}{BOLD}✅ {summary2}{RESET}")

                    conversation.append({"role": "assistant", "content": full_response2})

        except KeyboardInterrupt:
            print(f"\n  {YELLOW}Прервано пользователем{RESET}")
        except Exception as e:
            print(f"  {RED}[✗] Error: {str(e)}{RESET}")
            with open("error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
            print(f"  {RED}Текст ошибки сохранен в error.txt{RESET}")

        if len(conversation) > 30:
            conversation = [conversation[0]] + conversation[-20:]

        print()
        input(f"  {DIM}Press Enter to continue...{RESET}")


if __name__ == "__main__":
    main()
