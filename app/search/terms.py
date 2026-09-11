"""Turns a question into real search terms — shared by every search module so
GitHub, Jira, and Slack all treat filler words the same way.

Without this, a short word like "a" or "is" matches almost every file and
message as a substring, which floods results and drowns out the words that
actually matter — especially on short follow-up questions ("did that same
person work on anything else?") where filler words are most of the sentence.
"""

import string

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had", "has",
    "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "on",
    "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "would", "you", "your", "yours",
    "yourself", "yourselves",
    # extra filler common in typed questions, beyond the standard stop-word list
    "anything", "something", "someone", "anyone", "else", "also", "please",
    "thanks", "thank",
}


def search_terms(query: str) -> list[str]:
    """Lowercases and splits a question into its meaningful words.

    Strips leading/trailing punctuation from each word (e.g. "flow?" -> "flow")
    so a word typed with trailing punctuation still matches the same word
    elsewhere without it.

    Falls back to the unfiltered word list if filtering would remove
    everything, so a query that happens to be all filler words (rare, but
    possible) still searches on something instead of matching nothing.
    """
    words = [w.lower().strip(string.punctuation) for w in query.split()]
    words = [w for w in words if w]
    filtered = [w for w in words if w not in STOP_WORDS]
    return filtered or words
