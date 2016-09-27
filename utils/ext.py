import os
import sys

input = sys.argv[1]
pokemons = []

with open(input, "r") as f:
	for l in f:
		splits = l.split('\t')
		if len(splits) < 2:
			continue
		else:
			pokemons.append(splits[1])


output = open("../pokemons.txt", "w+")
for poke in pokemons:
	output.write(poke)
	output.write("\n")
output.close()
