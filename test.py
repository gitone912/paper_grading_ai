from pdf2image import convert_from_path

images = convert_from_path("/Users/pranaymishra/Desktop/neura_waves/paper_grading_ai/backend/papers/13629-JEE-Main-2025-Question-Paper-with-Solution-22-Jan-Shift-1-PDF_YiSBdZK.pdf", poppler_path="/opt/anaconda3/bin")
print(len(images))  # should show number of pages
