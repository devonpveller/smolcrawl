url = 'http://localhost:1313'
base_url = 'http://localhost:1313'
clean = url.replace(base_url, '').strip('/')

# Handle homepage/empty path
if not clean:
    clean = "index"

print(f'Clean after replace and strip: "{clean}"')
print(f'Length: {len(clean)}')
filename = clean + '.md'
print(f'Final filename: "{filename}"')

# Test other URLs too
urls = [
    'http://localhost:1313',
    'http://localhost:1313/',
    'http://localhost:1313/get-started/',
    'http://localhost:1313/guides/'
]

for test_url in urls:
    clean = test_url.replace(base_url, '').strip('/')
    # Handle homepage/empty path
    if not clean:
        clean = "index"
    filename = clean + '.md'
    print(f'{test_url} -> "{filename}"')
