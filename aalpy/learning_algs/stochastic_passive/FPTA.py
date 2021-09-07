from copy import deepcopy


class AlergiaPtaNode:

    def __init__(self, output):
        self.output = output
        self.frequency = 0
        self.children = dict()
        self.prefix = []
        # for visualization
        self.state_id = None
        self.children_prob = dict()

    def succs(self):
        return list(self.children.values())

    def __lt__(self, other):
        return len(self.prefix) < len(other.prefix)

    def __le__(self, other):
        return len(self.prefix) <= len(other.prefix)


def create_fpta(data, is_iofpta):
    root_node = AlergiaPtaNode(data[0][0])
    for seq in data:
        if seq[0] != root_node.output:
            print('All strings should have the same initial output')
            assert False
        curr_node = root_node

        for el in seq[1:]:
            input = el if not is_iofpta else (el[0], el[1])

            if input not in curr_node.children.keys():
                node = AlergiaPtaNode(el if not is_iofpta else el[1])
                node.prefix = list(curr_node.prefix)
                node.prefix.append(input)
                curr_node.children[input] = node

            curr_node = curr_node.children[input]
            curr_node.frequency += 1

    return root_node, deepcopy(root_node)