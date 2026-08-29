# 1. Fetch all updates from the remote server
git fetch origin

# 2. Create and switch to your new branch based on remote main
git checkout -b feature/F29 origin/main
# 3. Stage your modified files
git add .

# 4. Commit and save the changes locally on your feature branch
git commit -m "Your descriptive commit message here"
# 5. Push changes to your remote feature branch (for backup/review)
git push -u origin feature/F29

# 6. Push your feature branch directly into the remote main branch
git push origin feature/F29:main

## verify success
# 7. Fetch tracking updates and look at your commit log history
git fetch origin
git log --oneline -n 3

## To delete your feature branch after it has been safely merged

git switch main
git branch -d feature/F29
git push origin --delete feature/F29
git fetch origin --prune

