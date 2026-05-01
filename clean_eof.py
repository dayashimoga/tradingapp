def main():
    with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the FIRST occurrence of export default App;
    end_idx = content.find('export default App;')
    if end_idx != -1:
        # Keep everything up to export default App; and add it
        clean_content = content[:end_idx + len('export default App;')] + '\n'
        with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
            f.write(clean_content)
        print("Cleaned up App.jsx EOF!")

if __name__ == '__main__':
    main()
