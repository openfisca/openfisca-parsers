# -*- coding: utf-8 -*-

angry_rbnode = None
angry_state = None


class ParsingException(Exception):
    def __init__(self, message, rbnode, s):
        self.message = message
        self.rbnode = rbnode
        self.s = s

        global angry_rbnode
        global angry_state

        angry_rbnode = rbnode
        angry_state = s

        super(ParsingException).__init__(message)


class NotImplementedParsingError(ParsingException):
    pass


class AssertionParsingError(ParsingException):
    pass


class FunctionTooComplexException(ParsingException):
    pass


def my_assert(cond, rbnode, s, message=''):
    if cond:
        return

    raise AssertionParsingError(message, rbnode, s)
