from pathlib import Path

def generate_tree(dir_path, prefix=''):
    # ================= 配置区域 =================
    # 在这里添加你想过滤的文件或文件夹名称
    IGNORE_NAMES = {
        '__pycache__', 
        '.git', 
        '.idea', 
        '.vscode', 
        '__init__.py',   # <--- 这里是你要求增加的
        '.DS_Store'
    }
    # ===========================================

    path = Path(dir_path)
    
    try:
        # 获取所有文件/文件夹
        contents = list(path.iterdir())
    except PermissionError:
        return

    # 过滤掉在 IGNORE_NAMES 中的文件
    # 同时也过滤掉以点开头的隐藏文件（如果你想保留隐藏文件，删掉 'and not x.name.startswith('.')' 即可）
    contents = [
        x for x in contents 
        if x.name not in IGNORE_NAMES 
    ]
    
    # 排序：让文件夹和文件按字母顺序排列
    contents.sort(key=lambda x: x.name.lower())

    # 准备树枝形状
    # 指针数组：除了最后一个元素是 └── ，前面的都是 ├── 
    pointers = [('├── ', '│   ')] * (len(contents) - 1) + [('└── ', '    ')]

    for pointer, path_obj in zip(pointers, contents):
        # 打印当前行
        yield prefix + pointer[0] + path_obj.name

        if path_obj.is_dir():
            # 如果是文件夹，递归进入
            # pointer[1] 是下一级的缩进前缀（'│   ' 或 '    '）
            extension = pointer[1]
            yield from generate_tree(path_obj, prefix=prefix + extension)

if __name__ == '__main__':
    # '.' 代表当前目录，你可以改成绝对路径，例如 r'C:\Projects\MyCode'
    for line in generate_tree('.'):
        print(line)