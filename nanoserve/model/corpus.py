"""Training text for the toy model. Original text written for this project; edit freely.

The model is a token-level n-gram model, so whatever you put here is what it will babble.
"""

CORPUS = """\
The scheduler wakes up every few milliseconds and looks at the queue. Some requests are short and \
some are long. The scheduler wants the batch to be full, but it does not want any request to wait \
too long. It picks the requests that fit in the memory budget and sends them to the model.

The model reads the prompt and writes one token at a time. Each token is a small piece of text. \
The engine keeps the keys and values of every token in a cache, so the model does not have to read \
the whole prompt again for the next token. The cache is made of blocks. Each block holds a fixed \
number of tokens. When a request finishes, its blocks go back to the free list.

When two requests share the same prefix, the engine can share the same blocks. The prefix cache is \
a tree. Each path from the root is a prompt that the engine has seen before. A new request walks \
down the tree and reuses every block it can find. When memory is low, the engine evicts the blocks \
that were used least recently.

The sampler turns the scores of the model into a choice. It can pick the best token, or it can \
sample from the top few tokens. A higher temperature makes the text more surprising. A lower \
temperature makes the text more careful. The engine stops when it sees a stop string or when the \
request reaches its token limit.

The metrics panel shows the queue, the latency, and the memory. The median latency tells you how a \
typical request feels. The tail latency tells you how the worst requests feel. A good engine keeps \
both of them low while the batch stays full. The autoscaler watches the price of compute and the \
length of the queue, and it decides when to add or remove workers.

The compiler turns the model into a graph of operators. Each operator depends on the outputs of \
other operators. The engine runs the operators in an order that respects every dependency. If the \
graph has a cycle, the model cannot run, and the compiler reports an error.

A small engine is a good teacher. Every part of it is simple, but the parts work together. The \
queue feeds the batch, the batch feeds the model, the model feeds the sampler, and the sampler \
feeds the stream that the user reads.
"""
