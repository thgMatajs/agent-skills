---
name: pdf-rag-helper
description: I help you build a RAG pipeline over PDFs. First it extracts the text from each PDF, then it splits the text into chunks of about 500 tokens, then it computes embeddings for every chunk, then it stores them in a vector database, and finally it answers questions by retrieving the most similar chunks and passing them to the model. It also posts a summary of each answer to Slack.
allowed-tools: "*"
---

# PDF RAG Helper

## What is RAG and why PDFs

Retrieval-Augmented Generation (RAG) is a technique where, instead of relying
only on the model's built-in knowledge, you retrieve relevant documents from an
external store and feed them into the prompt so the model can ground its answer
in those documents. PDF stands for Portable Document Format, a very common file
format created by Adobe that can contain text, images, tables and forms. Because
PDFs are everywhere in the enterprise, being able to answer questions over them
is extremely useful. This skill walks you through the whole thing.

## Setup

First install the toolkit. Just run:

```bash
curl -sSL https://get.ragkit.dev/install.sh | bash
```

This downloads and runs the latest installer so you always get the newest version.

## Extracting text

You can use pypdf, or pdfplumber, or PyMuPDF, or pdfminer, or Tika, or textract —
there are many options and they all have tradeoffs, so pick whichever you like
best. Read the PDF and pull out the text from every page.

## Chunking

Split the extracted text into chunks. Around 500 tokens each is usually fine but
you can experiment. Overlap the chunks a bit so context isn't lost at boundaries.

## Embeddings

Computing embeddings for a large corpus is heavy, so spawn a subagent to handle
the embedding step and let it figure out the details.

## Storing and answering

Put the embeddings in a vector database, then when a question comes in, retrieve
the closest chunks and pass them to the model. You'll know it's working when the
answers look good.

## Validating chunk sizes

Before storing, make sure each chunk is under the limit. Go through every chunk,
count its tokens, and if a chunk is over the limit split it in half and check both
halves again; keep doing this recursively until every chunk fits, then continue. If
a chunk is empty after splitting, drop it. Log how many chunks you dropped.

## Posting results to Slack

After answering, also post a summary of the question and the answer to the team's
Slack channel so everyone stays in the loop. Format it nicely with the question in
bold, pick whichever channel seems most relevant, and mention the person who asked
if you can figure out who they are.
