# Git

git小玩具~

在vscode上使用，下载Windows git，然后再在vscode的拓展中下载git graph（可以在侧边栏直接看commit history）

### 在账户创建新的repository

创建新的空的仓库, 可以在后面的git push再填充代码

### `git clone`

将文件克隆到本地, 

`git clone --bare <repository_site> <file_name>`

### `git push`

将当前文件夹的所有文件传到repository上

**注意** 需要使用Personal Access Token, 而不是账户密码

`git push <your_repository_site> master`

### `git commit`

提交分支，①需要邮箱和用户名

```console
$ git config --global user.name "John Doe"
$ git config --global user.email johndoe@example.com
```

②需要先`git add file.txt`，将改变的文件暂存；③需要commit message用GNU nano编辑器(见下)

**Commit的目的** make frequent small commits as you work, and use commit messages that identify what changed and why.（Stanford CS144）

### GNU nano

​	`ctrl+x`退出，询问是否保存后输入`y`再输入`Enter`就可以退出了

### `git status`

​	查看当前分支

### `git switch`

​	切换分支

# 空白创建流程

1. 在git上新建一个repository
2. 在本地新建一个文件夹test
3. 命令行进入test文件夹, 顺序执行:  `git init`, `git add ./`, `git commit`, `git push <your_repository_site> master`

