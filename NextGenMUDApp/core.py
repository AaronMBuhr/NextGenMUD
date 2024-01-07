
class FlagBitmap:
    def __init__(self):
        self.flags = 0

    def set_flag(self, flag):
        self.flags |= flag

    def clear_flag(self, flag):
        self.flags &= ~flag

    def is_flag_set(self, flag):
        return bool(self.flags & flag)

