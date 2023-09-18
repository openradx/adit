from random import randint
from time import sleep
from typing import Any, Callable

import openai
import tiktoken
from openai.error import ServiceUnavailableError

ReportGeneratedCallback = Callable[[str, int], None]


# from https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613", silent=False):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        if not silent:
            print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        if not silent:
            print(
                "Warning: gpt-3.5-turbo may update over time. "
                "Returning num tokens assuming gpt-3.5-turbo-0613."
            )
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        if not silent:
            print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}.
            See https://github.com/openai/openai-python/blob/main/chatml.md for information on
            how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


class ReportGenerator:
    def __init__(
        self,
        api_key: str,
        model="gpt-3.5-turbo",
        max_tokens=4096,
        callback: ReportGeneratedCallback | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.callback = callback

        self.messages = [{"role": "system", "content": "You are an senior radiologist."}]

    def reset_context(self, full_reset=False):
        if len(self.messages) < 3 or full_reset:
            self.messages = [self.messages[0]]
        else:
            # Retain first question and last answer.
            self.messages = [self.messages[0], self.messages[1], self.messages[-1]]

    def generate_report(self, freshly=False) -> str:
        if freshly:
            self.reset_context(full_reset=True)

        if len(self.messages) == 1:
            self.messages.append({"role": "user", "content": "Write an example radiology report."})
        else:
            self.messages.append(
                {"role": "user", "content": "Write another example radiology report."}
            )

        token_count = num_tokens_from_messages(self.messages, self.model, silent=True)
        if token_count > self.max_tokens:
            self.reset_context()

        response: Any = None
        retries = 0
        while not response:
            try:
                response = openai.ChatCompletion.create(
                    model=self.model, messages=self.messages, api_key=self.api_key
                )
            except ServiceUnavailableError as err:
                retries += 1
                if retries == 3:
                    print("Error! Service unavailable even after 3 retries.")
                    raise err

                # maybe use rate limiter like https://github.com/tomasbasham/ratelimit
                sleep(randint(3, 10))

        answer = response.choices[0].message.content

        if self.callback:
            token_count = num_tokens_from_messages(self.messages, self.model, silent=True)
            self.callback(answer, token_count)

        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def generate_reports(self, num: int, freshly=False) -> list[str]:
        reports = []
        for i in range(num):
            report = self.generate_report(freshly=freshly)
            reports.append(report)

        return reports
